"""
OpenAI Assistants API Service
Manages assistants, vector stores, threads, and files
"""
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI

from config import config


class AssistantService:
    """Service for OpenAI Assistants API operations"""
    
    _instance = None
    
    logger = logging.getLogger(__name__)
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AssistantService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)
        self.assistant_id = None  # Will be set/loaded from config
        self._initialized = True
    
    # ============ Assistant Management ============
    
    def create_assistant(
        self,
        name: Optional[str] = None,
        instructions: Optional[str] = None,
        model: Optional[str] = None,
        tools: Optional[List[Dict]] = None,
        vector_store_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Create a new assistant"""
        name = name or config.DEFAULT_ASSISTANT_NAME
        instructions = instructions or config.DEFAULT_ASSISTANT_INSTRUCTIONS
        model = model or config.DEFAULT_ASSISTANT_MODEL
        tool_resources = {}
        if vector_store_ids:
            tool_resources["file_search"] = {"vector_store_ids": vector_store_ids}
        
        assistant = self.client.beta.assistants.create(
            name=name,
            instructions=instructions,
            model=model,
            tools=tools or [{"type": "file_search"}],
            tool_resources=tool_resources if tool_resources else None
        )
        
        self.assistant_id = assistant.id
        return {
            "id": assistant.id,
            "name": assistant.name,
            "model": assistant.model,
            "instructions": assistant.instructions,
            "tools": [tool.model_dump() if hasattr(tool, 'model_dump') else dict(tool) for tool in (assistant.tools or [])],
            "tool_resources": assistant.tool_resources.model_dump() if hasattr(assistant.tool_resources, 'model_dump') else (dict(assistant.tool_resources) if assistant.tool_resources else {})
        }
    
    def get_assistant(self, assistant_id: Optional[str] = None) -> Dict[str, Any]:
        """Get assistant details"""
        aid = assistant_id or self.assistant_id
        if not aid:
            raise ValueError("No assistant ID provided")
        
        assistant = self.client.beta.assistants.retrieve(aid)
        return {
            "id": assistant.id,
            "name": assistant.name,
            "model": assistant.model,
            "instructions": assistant.instructions,
            "tools": [tool.model_dump() if hasattr(tool, 'model_dump') else dict(tool) for tool in (assistant.tools or [])],
            "tool_resources": assistant.tool_resources.model_dump() if hasattr(assistant.tool_resources, 'model_dump') else (dict(assistant.tool_resources) if assistant.tool_resources else {})
        }
    
    def update_assistant(
        self,
        assistant_id: Optional[str] = None,
        name: Optional[str] = None,
        instructions: Optional[str] = None,
        model: Optional[str] = None,
        tools: Optional[List[Dict]] = None,
        vector_store_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Update assistant configuration"""
        aid = assistant_id or self.assistant_id
        if not aid:
            raise ValueError("No assistant ID provided")
        
        update_data = {}
        if name:
            update_data["name"] = name
        if instructions:
            update_data["instructions"] = instructions
        if model:
            update_data["model"] = model
        if tools:
            update_data["tools"] = tools
        if vector_store_ids is not None:
            update_data["tool_resources"] = {
                "file_search": {"vector_store_ids": vector_store_ids}
            }
        
        assistant = self.client.beta.assistants.update(aid, **update_data)
        return {
            "id": assistant.id,
            "name": assistant.name,
            "model": assistant.model,
            "instructions": assistant.instructions,
            "tools": [tool.model_dump() if hasattr(tool, 'model_dump') else dict(tool) for tool in (assistant.tools or [])],
            "tool_resources": assistant.tool_resources.model_dump() if hasattr(assistant.tool_resources, 'model_dump') else (dict(assistant.tool_resources) if assistant.tool_resources else {})
        }
    
    def list_assistants(self, limit: int = 20) -> List[Dict[str, Any]]:
        """List all assistants"""
        assistants = self.client.beta.assistants.list(limit=limit)
        return [{
            "id": a.id,
            "name": a.name,
            "model": a.model,
            "created_at": a.created_at
        } for a in assistants.data]
    
    def delete_assistant(self, assistant_id: str) -> bool:
        """Delete an assistant"""
        response = self.client.beta.assistants.delete(assistant_id)
        return response.deleted
    
    def ensure_assistant_id(self, assistant_id: Optional[str] = None) -> str:
        """
        Ensure we have a valid assistant_id. If the provided ID is invalid or missing,
        reuse a cached assistant, fall back to the first available assistant, or create a new one.
        """
        candidate_ids = [assistant_id, getattr(self, "assistant_id", None)]
        for candidate in candidate_ids:
            if not candidate:
                continue
            try:
                self.get_assistant(candidate)
                self.assistant_id = candidate
                self.logger.info("Using assistant_id: %s", candidate)
                return candidate
            except Exception as exc:
                self.logger.warning("Assistant ID %s invalid or unavailable: %s", candidate, exc)
        
        # Try to reuse an existing assistant from the list
        try:
            assistants = self.list_assistants(limit=1)
            if assistants:
                self.assistant_id = assistants[0]["id"]
                self.logger.info("Using existing assistant from list: %s", self.assistant_id)
                return self.assistant_id
        except Exception as exc:
            self.logger.warning("Failed to list assistants: %s", exc)
        
        # Create a default assistant as a last resort
        self.logger.info("Creating default assistant for conversation")
        created = self.create_assistant()
        self.assistant_id = created["id"]
        self.logger.info("Created assistant: %s", self.assistant_id)
        return self.assistant_id
    
    def prepare_conversation(
        self,
        assistant_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        force_new_thread: bool = False
    ) -> Tuple[str, str, bool]:
        """
        Ensure assistant and thread IDs are valid. Creates new resources if needed.
        
        Returns:
            (assistant_id, thread_id, thread_created)
        """
        resolved_assistant_id = self.ensure_assistant_id(assistant_id)
        
        resolved_thread_id = None
        thread_created = False
        
        if thread_id and not force_new_thread:
            if thread_id.startswith("thread_"):
                try:
                    # Verify thread exists by retrieving a small slice of messages
                    self.get_thread_messages(thread_id, limit=1)
                    resolved_thread_id = thread_id
                    self.logger.info("Using existing thread_id: %s", thread_id)
                except Exception as exc:
                    self.logger.warning("Existing thread_id %s invalid: %s", thread_id, exc)
            else:
                self.logger.warning("Provided thread_id '%s' is invalid - creating new thread", thread_id)
        
        if force_new_thread or not resolved_thread_id:
            resolved_thread_id = self.create_thread()
            thread_created = True
            self.logger.info("Created new thread_id: %s", resolved_thread_id)
        
        return resolved_assistant_id, resolved_thread_id, thread_created
    
    # ============ Vector Store Management ============
    
    def create_vector_store(self, name: str, file_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """Create a new vector store"""
        create_params = {"name": name}
        if file_ids:
            create_params["file_ids"] = file_ids
        vector_store = self.client.vector_stores.create(**create_params)
        return {
            "id": vector_store.id,
            "name": vector_store.name,
            "status": vector_store.status,
            "file_counts": vector_store.file_counts.model_dump() if hasattr(vector_store.file_counts, 'model_dump') else dict(vector_store.file_counts) if vector_store.file_counts else {},
            "created_at": vector_store.created_at
        }
    
    def get_vector_store(self, vector_store_id: str) -> Dict[str, Any]:
        """Get vector store details"""
        vs = self.client.vector_stores.retrieve(vector_store_id)
        return {
            "id": vs.id,
            "name": vs.name,
            "status": vs.status,
            "file_counts": vs.file_counts.model_dump() if hasattr(vs.file_counts, 'model_dump') else dict(vs.file_counts) if vs.file_counts else {},
            "created_at": vs.created_at
        }
    
    def list_vector_stores(self, limit: int = 20) -> List[Dict[str, Any]]:
        """List all vector stores"""
        stores = self.client.vector_stores.list(limit=limit)
        return [{
            "id": vs.id,
            "name": vs.name,
            "status": vs.status,
            "file_counts": vs.file_counts.model_dump() if hasattr(vs.file_counts, 'model_dump') else dict(vs.file_counts) if vs.file_counts else {},
            "created_at": vs.created_at
        } for vs in stores.data]
    
    def update_vector_store(self, vector_store_id: str, name: str) -> Dict[str, Any]:
        """Update vector store name"""
        vs = self.client.vector_stores.update(vector_store_id, name=name)
        return {
            "id": vs.id,
            "name": vs.name,
            "status": vs.status,
            "file_counts": vs.file_counts.model_dump() if hasattr(vs.file_counts, 'model_dump') else dict(vs.file_counts) if vs.file_counts else {}
        }
    
    def delete_vector_store(self, vector_store_id: str) -> bool:
        """Delete a vector store"""
        response = self.client.vector_stores.delete(vector_store_id)
        return response.deleted
    
    # ============ File Management ============
    
    def upload_file(self, file_path: str, purpose: str = "assistants") -> str:
        """Upload a file to OpenAI"""
        self.logger.debug("Uploading file", extra={"path": file_path, "purpose": purpose})
        with open(file_path, "rb") as f:
            file = self.client.files.create(file=f, purpose=purpose)
        self.logger.info("Uploaded file", extra={"file_id": getattr(file, "id", None), "file_name": getattr(file, "filename", None), "status": getattr(file, "status", None)})
        return file.id
    
    def upload_file_from_bytes(self, file_bytes: bytes, filename: str, purpose: str = "assistants") -> str:
        """Upload a file from bytes"""
        self.logger.debug("Uploading file from bytes", extra={
            "file_name": filename,
            "size_bytes": len(file_bytes),
            "purpose": purpose
        })
        file = self.client.files.create(
            file=(filename, file_bytes),
            purpose=purpose
        )
        self.logger.info("Uploaded file from bytes", extra={
            "file_id": getattr(file, "id", None),
            "file_name": filename,
            "status": getattr(file, "status", None)
        })
        return file.id
    
    def list_files(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List all uploaded files"""
        files = self.client.files.list(limit=limit)
        return [{
            "id": f.id,
            "filename": f.filename,
            "bytes": f.bytes,
            "created_at": f.created_at,
            "purpose": f.purpose
        } for f in files.data]
    
    def get_file(self, file_id: str) -> Dict[str, Any]:
        """Get file details"""
        file_info = self.client.files.retrieve(file_id)
        return {
            "id": file_info.id,
            "filename": file_info.filename,
            "bytes": file_info.bytes,
            "created_at": file_info.created_at,
            "purpose": file_info.purpose
        }
    
    def add_file_to_vector_store(self, vector_store_id: str, file_id: str) -> Dict[str, Any]:
        """Add a file to a vector store and wait for ingestion to complete."""
        self.logger.debug("Adding file to vector store", extra={"vector_store_id": vector_store_id, "file_id": file_id})
        vs_file = self.client.vector_stores.files.create(
            vector_store_id=vector_store_id,
            file_id=file_id
        )
        self.logger.info(
            "Queued file %s for ingestion into vector store %s (status=%s)",
            file_id,
            vector_store_id,
            getattr(vs_file, "status", "unknown")
        )
        terminal_statuses = {"completed", "failed", "cancelled"}
        attempts = 0
        max_attempts = 30
        wait_seconds = 1.0
        status = getattr(vs_file, "status", None)

        while status not in terminal_statuses and attempts < max_attempts:
            attempts += 1
            time.sleep(wait_seconds)
            vs_file = self.client.vector_stores.files.retrieve(
                vector_store_id=vector_store_id,
                file_id=vs_file.id
            )
            status = getattr(vs_file, "status", None)
            self.logger.debug(
                "Ingestion poll %d for file %s in vector store %s: status=%s",
                attempts,
                file_id,
                vector_store_id,
                status
            )

        if status != "completed":
            error_detail = getattr(vs_file, "last_error", None)
            message = "Unknown error"
            if isinstance(error_detail, dict):
                message = error_detail.get("message") or json.dumps(error_detail)
            elif error_detail:
                message = str(error_detail)
            self.logger.error(
                "File ingestion failed for file %s in vector store %s: status=%s, error=%s",
                file_id,
                vector_store_id,
                status,
                message
            )
            raise RuntimeError(f"File ingestion failed with status '{status}'. Details: {message}")

        self.logger.info(
            "File %s ingested successfully into vector store %s",
            file_id,
            vector_store_id
        )

        return {
            "id": vs_file.id,
            "vector_store_id": vs_file.vector_store_id,
            "status": vs_file.status,
            "created_at": vs_file.created_at
        }
    
    def list_vector_store_files(self, vector_store_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """List files in a vector store"""
        files = self.client.vector_stores.files.list(
            vector_store_id=vector_store_id,
            limit=limit
        )
        
        result = []
        for f in files.data:
            # Get file details
            try:
                file_info = self.client.files.retrieve(f.id)
                result.append({
                    "id": f.id,
                    "vector_store_id": f.vector_store_id,
                    "status": f.status,
                    "filename": file_info.filename,
                    "bytes": file_info.bytes,
                    "created_at": f.created_at
                })
            except Exception as e:
                self.logger.warning("Error retrieving file %s: %s", f.id, e)
                result.append({
                    "id": f.id,
                    "vector_store_id": f.vector_store_id,
                    "status": f.status,
                    "created_at": f.created_at
                })
        
        return result
    
    def delete_vector_store_file(self, vector_store_id: str, file_id: str) -> bool:
        """Remove a file from a vector store"""
        response = self.client.vector_stores.files.delete(
            vector_store_id=vector_store_id,
            file_id=file_id
        )
        return response.deleted
    
    def delete_file(self, file_id: str) -> bool:
        """Delete a file from OpenAI"""
        response = self.client.files.delete(file_id)
        return response.deleted
    
    # ============ Thread Management ============
    
    def create_thread(self, messages: Optional[List[Dict]] = None) -> str:
        """Create a new conversation thread"""
        thread = self.client.beta.threads.create(messages=messages or [])
        return thread.id
    
    def add_message_to_thread(self, thread_id: str, content: str, role: str = "user") -> Dict[str, Any]:
        """Add a message to a thread"""
        message = self.client.beta.threads.messages.create(
            thread_id=thread_id,
            role=role,
            content=content
        )
        return {
            "id": message.id,
            "thread_id": message.thread_id,
            "role": message.role,
            "content": message.content
        }
    
    def get_thread_messages(self, thread_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get messages from a thread"""
        messages = self.client.beta.threads.messages.list(
            thread_id=thread_id,
            limit=limit,
            order="asc"
        )
        
        result = []
        for msg in messages.data:
            content_text = ""
            if msg.content:
                for block in msg.content:
                    if hasattr(block, 'text'):
                        content_text += block.text.value
            
            result.append({
                "id": msg.id,
                "role": msg.role,
                "content": content_text,
                "created_at": msg.created_at
            })
        
        return result
    
    def delete_thread(self, thread_id: str) -> bool:
        """Delete a thread"""
        response = self.client.beta.threads.delete(thread_id)
        return response.deleted
    
    # ============ Run Management (Conversation) ============
    
    def run_assistant(
        self,
        thread_id: str,
        assistant_id: Optional[str] = None,
        instructions: Optional[str] = None
    ) -> str:
        """Start a run on a thread"""
        aid = assistant_id or self.assistant_id
        if not aid:
            raise ValueError("No assistant ID provided")
        
        run = self.client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=aid,
            instructions=instructions
        )
        return run.id
    
    def get_run_status(self, thread_id: str, run_id: str) -> Dict[str, Any]:
        """Get run status"""
        run = self.client.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=run_id
        )
        return {
            "id": run.id,
            "status": run.status,
            "created_at": run.created_at,
            "completed_at": run.completed_at,
            "failed_at": run.failed_at,
            "last_error": run.last_error
        }
    
    def wait_for_run_completion(
        self,
        thread_id: str,
        run_id: str,
        timeout: int = 60
    ) -> Dict[str, Any]:
        """Wait for run to complete and return final status"""
        import time
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            run_status = self.get_run_status(thread_id, run_id)
            
            if run_status["status"] in ["completed", "failed", "cancelled", "expired"]:
                return run_status
            
            time.sleep(0.5)  # Poll every 500ms
        
        return {"status": "timeout"}
    
    def get_run_response(self, thread_id: str, run_id: str) -> Optional[str]:
        """Get the assistant's response after a run completes"""
        # Wait for completion
        run_status = self.wait_for_run_completion(thread_id, run_id)
        
        if run_status["status"] != "completed":
            return None
        
        # Get the latest messages in descending order (newest first)
        messages = self.client.beta.threads.messages.list(
            thread_id=thread_id,
            limit=10,
            order="desc"
        )
        
        # Find the first assistant message (which is the latest)
        for msg in messages.data:
            if msg.role == "assistant":
                content_text = ""
                if msg.content:
                    for block in msg.content:
                        if hasattr(block, 'text'):
                            content_text += block.text.value
                return content_text
        
        return None
    
    # ============ Convenience Methods ============
    
    def chat_with_assistant(
        self,
        message: str,
        thread_id: Optional[str] = None,
        assistant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Simplified chat interface
        Returns: {"thread_id": str, "response": str, "message_id": str}
        """
        # Create or use existing thread
        if not thread_id:
            thread_id = self.create_thread()
        
        # Add user message
        self.add_message_to_thread(thread_id, message)
        
        # Run assistant
        run_id = self.run_assistant(thread_id, assistant_id)
        
        # Get response
        response = self.get_run_response(thread_id, run_id)
        
        return {
            "thread_id": thread_id,
            "response": response,
            "run_id": run_id
        }
    
    def chat_with_assistant_stream(
        self,
        message: str,
        thread_id: Optional[str] = None,
        assistant_id: Optional[str] = None
    ):
        """
        Streaming chat interface using Assistant API
        Yields: {"type": "thread_id", "thread_id": str} or {"type": "text", "text": str} or {"type": "done"}
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Create or use existing thread
        if not thread_id:
            thread_id = self.create_thread()
        
        # Yield thread_id first
        yield {"type": "thread_id", "thread_id": thread_id}
        
        # Add user message
        self.add_message_to_thread(thread_id, message)
        
        # Use the assistant_id if provided
        current_assistant_id = assistant_id or self.assistant_id
        if not current_assistant_id:
            raise ValueError("No assistant_id provided")
        
        logger.info(f"Starting streaming run with assistant {current_assistant_id} on thread {thread_id}")
        
        # Create a streaming run
        try:
            with self.client.beta.threads.runs.stream(
                thread_id=thread_id,
                assistant_id=current_assistant_id
            ) as stream:
                for event in stream:
                    # Handle text deltas (streaming text chunks)
                    if event.event == 'thread.message.delta':
                        for content in event.data.delta.content:
                            if content.type == 'text':
                                text_delta = content.text.value
                                logger.debug(f"Streaming text delta: {text_delta}")
                                yield {"type": "text", "text": text_delta}
                    
                    # Handle completion
                    elif event.event == 'thread.run.completed':
                        logger.info("Streaming run completed")
                        yield {"type": "done"}
                        break
                    
                    # Handle errors
                    elif event.event == 'thread.run.failed':
                        logger.error(f"Run failed: {event.data}")
                        yield {"type": "error", "error": "Assistant run failed"}
                        break
        except Exception as e:
            logger.exception("Error during streaming")
            yield {"type": "error", "error": str(e)}

