"""Response service -- stateless response chaining with server-side tool loop.

Replaces ChatService. Each API call creates one Response that may contain
multiple LLM rounds (tool calls executed server-side).
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError
from src.llm import LLMGateway, get_llm_gateway, Message as LLMMessage
from src.llm.providers.base import ToolCall
from src.llm.tool_resolver import ToolResolver
from src.models.assistant import Assistant
from src.models.conversation import Conversation
from src.models.knowledge_base import KnowledgeBase
from src.models.response import Response, ResponseItem
from src.models.usage import UsageLog
from src.schemas.response import CreateResponseRequest
from src.services.rag_query_service import RAGQueryService
from src.tools import ToolExecutor

logger = logging.getLogger(__name__)


class ResponseService:
    """Creates responses with multi-round tool loops and history chaining."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.gateway = get_llm_gateway()
        self.rag_query = RAGQueryService(db)

    async def create_response_stream(
        self,
        user_id: UUID | None,
        request: CreateResponseRequest,
    ) -> AsyncGenerator[str, None]:
        """Create a response and stream SSE events.

        Yields SSE-formatted strings: "data: {json}\n\n"
        """
        # 1. Resolve assistant and apply overrides
        assistant = await self._get_assistant(request.assistant_id)
        model = request.model or assistant.model
        provider = request.provider or assistant.provider
        instructions = request.instructions or assistant.system_prompt
        temperature = request.temperature if request.temperature is not None else float(assistant.temperature)
        max_tokens = request.max_tokens or assistant.max_tokens
        tool_ids = request.tool_ids if request.tool_ids is not None else list(assistant.tool_ids)
        kb_ids = request.knowledge_base_ids if request.knowledge_base_ids is not None else list(assistant.knowledge_base_ids)

        # 2. Get or create conversation
        conversation = await self._get_or_create_conversation(
            user_id=user_id,
            conversation_id=request.conversation_id,
            assistant_id=request.assistant_id,
        )

        # 3. Create Response record
        response = Response(
            user_id=user_id,
            assistant_id=assistant.id,
            conversation_id=conversation.id,
            previous_response_id=request.previous_response_id,
            model=model,
            provider=provider,
            instructions=instructions,
            temperature=temperature,
            max_tokens=max_tokens,
            tool_ids=tool_ids,
            knowledge_base_ids=[str(kb) for kb in kb_ids],
            max_tool_rounds=request.max_tool_rounds,
            status="in_progress",
            response_metadata=request.metadata,
        )
        self.db.add(response)
        await self.db.flush()
        await self.db.refresh(response)

        # 4. Save input items
        seq = 0
        for item in request.input:
            if item.type == "message":
                ri = ResponseItem(
                    response_id=response.id,
                    sequence_order=seq,
                    item_type="message",
                    direction="input",
                    role=item.role or "user",
                    content=item.content or "",
                )
            else:
                ri = ResponseItem(
                    response_id=response.id,
                    sequence_order=seq,
                    item_type="function_call_output",
                    direction="input",
                    call_id=item.call_id,
                    function_output=item.output,
                )
            self.db.add(ri)
            seq += 1
        await self.db.flush()

        # 5. Emit response.created
        yield self._sse({
            "type": "response.created",
            "response": {
                "id": str(response.id),
                "conversation_id": str(conversation.id),
                "status": "in_progress",
            },
        })

        try:
            # 6. Load history from previous_response_id chain
            history_items = await self._load_history(request.previous_response_id)

            # 7. RAG retrieval
            rag_context = ""
            if kb_ids:
                rag_context = await self._get_rag_context(
                    query=self._extract_user_query(request),
                    knowledge_base_ids=kb_ids,
                )
                if rag_context:
                    rag_item = ResponseItem(
                        response_id=response.id,
                        sequence_order=seq,
                        item_type="rag_context",
                        direction="output",
                        rag_sources=[{"context": rag_context}],
                    )
                    self.db.add(rag_item)
                    await self.db.flush()
                    seq += 1
                    yield self._sse({
                        "type": "response.output_item.added",
                        "item": {
                            "id": str(rag_item.id),
                            "type": "rag_context",
                        },
                    })

            # 8. Build tools
            resolved = await self._build_tools(tool_ids, provider, model)
            tools = resolved.tools if resolved else None
            connectors = resolved.connectors if resolved else None

            # 9. Tool loop
            total_input_tokens = 0
            total_output_tokens = 0
            current_items: list[ResponseItem] = []

            # Load current response items for context
            await self.db.refresh(response)
            current_items = list(response.items or [])

            for round_num in range(request.max_tool_rounds):
                # Build LLM messages
                messages = self._build_llm_messages(
                    instructions=instructions,
                    rag_context=rag_context,
                    history_items=history_items,
                    current_items=current_items,
                )

                # Stream LLM
                full_content = ""
                tool_calls: list[ToolCall] = []
                round_input_tokens = 0
                round_output_tokens = 0

                # Add assistant message item placeholder
                asst_item = ResponseItem(
                    response_id=response.id,
                    sequence_order=seq,
                    item_type="message",
                    direction="output",
                    role="assistant",
                    content="",
                )
                self.db.add(asst_item)
                await self.db.flush()
                await self.db.refresh(asst_item)
                seq += 1

                yield self._sse({
                    "type": "response.output_item.added",
                    "item": {
                        "id": str(asst_item.id),
                        "type": "message",
                        "role": "assistant",
                    },
                })

                async for delta in self.gateway.stream(
                    messages=messages,
                    model=model,
                    provider=provider,
                    temperature=temperature,
                    max_tokens=max_tokens or 4096,
                    tools=tools,
                    connectors=connectors,
                ):
                    if delta.type == "text":
                        full_content += delta.content or ""
                        yield self._sse({
                            "type": "response.content.delta",
                            "delta": delta.content,
                        })
                    elif delta.type == "tool_call":
                        if delta.tool_call:
                            tool_calls.append(delta.tool_call)
                    elif delta.type == "finish":
                        if delta.input_tokens:
                            round_input_tokens = delta.input_tokens
                        if delta.output_tokens:
                            round_output_tokens = delta.output_tokens

                total_input_tokens += round_input_tokens
                total_output_tokens += round_output_tokens

                # Update assistant message item
                asst_item.content = full_content
                await self.db.flush()

                if full_content:
                    yield self._sse({
                        "type": "response.content.done",
                        "text": full_content,
                    })

                current_items.append(asst_item)

                # If no tool calls, we're done
                if not tool_calls:
                    break

                # Save function_call items and execute tools
                for tc in tool_calls:
                    fn_name = tc.name or (tc.function or {}).get("name", "")
                    fn_args = tc.arguments or (tc.function or {}).get("arguments", "")
                    call_id = tc.id

                    # Save function_call item
                    fc_item = ResponseItem(
                        response_id=response.id,
                        sequence_order=seq,
                        item_type="function_call",
                        direction="output",
                        call_id=call_id,
                        function_name=fn_name,
                        function_arguments=fn_args,
                    )
                    self.db.add(fc_item)
                    await self.db.flush()
                    await self.db.refresh(fc_item)
                    seq += 1

                    yield self._sse({
                        "type": "response.output_item.added",
                        "item": {
                            "id": str(fc_item.id),
                            "type": "function_call",
                            "name": fn_name,
                            "call_id": call_id,
                        },
                    })
                    yield self._sse({
                        "type": "response.function_call_arguments.done",
                        "call_id": call_id,
                        "name": fn_name,
                        "arguments": fn_args,
                    })

                    current_items.append(fc_item)

                    # Execute tool server-side
                    output = await self._execute_tool(
                        fn_name, fn_args, fc_item.id,
                    )

                    # Save function_call_output item
                    fco_item = ResponseItem(
                        response_id=response.id,
                        sequence_order=seq,
                        item_type="function_call_output",
                        direction="output",
                        call_id=call_id,
                        function_output=output,
                    )
                    self.db.add(fco_item)
                    await self.db.flush()
                    await self.db.refresh(fco_item)
                    seq += 1

                    yield self._sse({
                        "type": "response.output_item.added",
                        "item": {
                            "id": str(fco_item.id),
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": output,
                        },
                    })

                    current_items.append(fco_item)

                # Reset for next round (LLM will see tool results)
                full_content = ""
                tool_calls = []

            # Determine status reason
            status_reason = "stop"
            if tool_calls:
                status_reason = "max_tool_rounds"

            # 10. Finalize response
            now = datetime.now(timezone.utc)
            response.status = "completed"
            response.status_reason = status_reason
            response.input_tokens = total_input_tokens
            response.output_tokens = total_output_tokens
            response.total_tokens = total_input_tokens + total_output_tokens
            response.completed_at = now
            await self.db.flush()

            # 11. Update conversation
            conversation.latest_response_id = response.id
            conversation.response_count = (conversation.response_count or 0) + 1
            if not conversation.title:
                conversation.title = self._generate_title(request)
            await self.db.flush()

            # 12. Log usage
            await self._log_usage(
                user_id=user_id,
                assistant_id=assistant.id,
                conversation_id=conversation.id,
                response_id=response.id,
                provider=provider,
                model=model,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
            )

            # 13. Analyze emotion
            last_content = ""
            for item in reversed(current_items):
                if item.item_type == "message" and item.role == "assistant" and item.content:
                    last_content = item.content
                    break
            emotion = self._analyze_emotion(last_content)

            # 14. Emit response.completed
            yield self._sse({
                "type": "response.completed",
                "response": {
                    "id": str(response.id),
                    "conversation_id": str(conversation.id),
                    "status": "completed",
                    "usage": {
                        "input_tokens": total_input_tokens,
                        "output_tokens": total_output_tokens,
                        "total_tokens": total_input_tokens + total_output_tokens,
                    },
                    "emotion": emotion,
                },
            })

        except Exception as e:
            logger.exception("Response failed: %s", e)
            response.status = "failed"
            response.error_code = "internal_error"
            response.error_message = str(e)
            await self.db.flush()

            yield self._sse({
                "type": "response.failed",
                "error": {"code": "internal_error", "message": str(e)},
            })

    async def get_response(self, response_id: UUID) -> Response:
        """Get a response by ID."""
        result = await self.db.execute(
            select(Response).where(
                Response.id == response_id,
            )
        )
        response = result.scalar_one_or_none()
        if not response:
            raise NotFoundError(message="Response not found", resource="response")
        return response

    async def delete_response(self, response_id: UUID) -> None:
        """Delete a response."""
        response = await self.get_response(response_id)
        await self.db.delete(response)
        await self.db.flush()

    async def list_conversation_responses(
        self, conversation_id: UUID, limit: int = 50,
    ) -> list[Response]:
        """List responses in a conversation."""
        # Verify conversation exists
        conv_result = await self.db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
            )
        )
        if not conv_result.scalar_one_or_none():
            raise NotFoundError(message="Conversation not found", resource="conversation")

        result = await self.db.execute(
            select(Response)
            .where(Response.conversation_id == conversation_id)
            .order_by(Response.created_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    # ==================== Private helpers ====================

    def _sse(self, data: dict) -> str:
        """Format as SSE event."""
        return f"data: {json.dumps(data)}\n\n"

    def _extract_user_query(self, request: CreateResponseRequest) -> str:
        """Extract the user query from input items."""
        for item in reversed(request.input):
            if item.type == "message" and item.role == "user" and item.content:
                return item.content
        return ""

    def _generate_title(self, request: CreateResponseRequest) -> str:
        """Generate a title from the first user message."""
        query = self._extract_user_query(request)
        if query:
            return query[:100] + ("..." if len(query) > 100 else "")
        return "New Conversation"

    async def _get_assistant(self, assistant_id: UUID) -> Assistant:
        result = await self.db.execute(
            select(Assistant).where(Assistant.id == assistant_id)
        )
        assistant = result.scalar_one_or_none()
        if not assistant:
            raise NotFoundError(message="Assistant not found", resource="assistant")
        return assistant

    async def _get_or_create_conversation(
        self,
        user_id: UUID | None,
        conversation_id: UUID | None,
        assistant_id: UUID,
    ) -> Conversation:
        if conversation_id:
            result = await self.db.execute(
                select(Conversation).where(
                    Conversation.id == conversation_id,
                )
            )
            conv = result.scalar_one_or_none()
            if conv:
                return conv

        conversation = Conversation(
            user_id=user_id,
            assistant_id=assistant_id,
            status="active",
        )
        self.db.add(conversation)
        await self.db.flush()
        await self.db.refresh(conversation)
        return conversation

    async def _load_history(self, previous_response_id: UUID | None) -> list[ResponseItem]:
        """Walk the response chain and collect all items for LLM context."""
        if not previous_response_id:
            return []

        # Collect response chains in reverse order, then flatten
        chain_segments: list[list[ResponseItem]] = []
        current_id = previous_response_id
        max_chain_depth = 100  # safety limit

        for _ in range(max_chain_depth):
            if not current_id:
                break
            result = await self.db.execute(
                select(Response).where(Response.id == current_id)
            )
            resp = result.scalar_one_or_none()
            if not resp:
                logger.warning("Response %s not found in history chain", current_id)
                break

            chain_segments.append(list(resp.items or []))
            current_id = resp.previous_response_id

        # Reverse to chronological order and flatten (O(n) instead of O(n²))
        chain_segments.reverse()
        all_items: list[ResponseItem] = []
        for segment in chain_segments:
            all_items.extend(segment)

        return all_items

    def _build_llm_messages(
        self,
        instructions: str,
        rag_context: str,
        history_items: list[ResponseItem],
        current_items: list[ResponseItem],
    ) -> list[LLMMessage]:
        """Build the LLM message list from instructions + items."""
        messages: list[LLMMessage] = []

        # System message
        system_content = instructions
        if rag_context:
            system_content += f"\n\n## Relevant Context:\n{rag_context}"
        messages.append(LLMMessage(role="system", content=system_content))

        # Convert items to LLM messages
        for item in history_items + current_items:
            msg = self._item_to_llm_message(item)
            if msg:
                messages.append(msg)

        return messages

    def _item_to_llm_message(self, item: ResponseItem) -> LLMMessage | None:
        """Convert a ResponseItem to an LLM Message."""
        if item.item_type == "message":
            return LLMMessage(role=item.role or "user", content=item.content or "")

        if item.item_type == "function_call":
            return LLMMessage(
                role="assistant",
                content="",
                tool_calls=[{
                    "id": item.call_id or "",
                    "type": "function",
                    "function": {
                        "name": item.function_name or "",
                        "arguments": item.function_arguments or "",
                    },
                }],
            )

        if item.item_type == "function_call_output":
            return LLMMessage(
                role="tool",
                content=item.function_output or "",
                tool_call_id=item.call_id or "",
            )

        # rag_context items are already included in the system message
        return None

    async def _get_rag_context(
        self, query: str, knowledge_base_ids: list[UUID], top_k: int = 5,
    ) -> str:
        if not knowledge_base_ids:
            return ""

        platform_kb_ids = await self._get_platform_managed_kb_ids(knowledge_base_ids)
        if not platform_kb_ids:
            return ""

        result = await self.rag_query.query(
            query=query,
            knowledge_base_ids=platform_kb_ids,
            top_k=top_k,
            score_threshold=0.5,
        )
        return self.rag_query.format_context(result.results)

    async def _get_platform_managed_kb_ids(self, kb_ids: list[UUID]) -> list[UUID]:
        if not kb_ids:
            return []
        result = await self.db.execute(
            select(KnowledgeBase.id).where(
                KnowledgeBase.id.in_(kb_ids),
                KnowledgeBase.kb_type == "platform_managed",
            )
        )
        return list(result.scalars().all())

    async def _build_tools(
        self, tool_ids: list[str], provider: str, model: str,
    ):
        if not tool_ids:
            return None
        resolver = ToolResolver(self.db)
        result = await resolver.resolve(
            tool_refs=tool_ids,
            provider=provider,
            model=model,
        )
        return result if result.tools or result.connectors else None

    async def _execute_tool(
        self,
        function_name: str,
        function_arguments: str,
        fc_item_id: UUID,
    ) -> str:
        """Execute a tool and return the output as a string."""
        from src.models.tool import Tool

        try:
            query = select(Tool).where(
                Tool.name == function_name,
                Tool.is_active == True,
            )
            result = await self.db.execute(query)
            tool = result.scalar_one_or_none()

            if not tool:
                return json.dumps({"error": f"Tool not found: {function_name}"})

            executor = ToolExecutor(tool, self.db)
            args = json.loads(function_arguments) if function_arguments else {}
            output = await executor.execute(response_item_id=fc_item_id, **args)
            return json.dumps(output) if not isinstance(output, str) else output

        except Exception as e:
            logger.warning("Tool execution failed: %s", e)
            return json.dumps({"error": str(e)})

    async def _log_usage(
        self,
        user_id: UUID | None,
        assistant_id: UUID,
        conversation_id: UUID,
        response_id: UUID,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        usage = UsageLog(
            user_id=user_id,
            assistant_id=assistant_id,
            conversation_id=conversation_id,
            response_id=response_id,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            request_type="chat",
        )
        self.db.add(usage)
        await self.db.flush()

    def _analyze_emotion(self, text: str) -> str:
        """Simple keyword-based emotion detection."""
        text_lower = text.lower()
        emotions = {
            "happy": ["happy", "glad", "great", "wonderful", "excited", "joy"],
            "sad": ["sad", "sorry", "unfortunate", "regret", "apologize"],
            "excited": ["amazing", "incredible", "fantastic", "awesome"],
            "calm": ["understand", "certainly", "of course", "sure"],
            "concerned": ["worried", "concern", "issue", "problem", "error"],
        }

        scores = {emotion: 0 for emotion in emotions}
        for emotion, keywords in emotions.items():
            for keyword in keywords:
                if keyword in text_lower:
                    scores[emotion] += 1

        max_emotion = max(scores, key=scores.get)
        return max_emotion if scores[max_emotion] > 0 else "friendly"
