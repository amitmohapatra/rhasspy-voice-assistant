"""Real-time conversation WebSocket API with VAD and interruption support.

This module provides WebSocket endpoints for:
- Real-time voice conversation with VAD
- Audio streaming for both user and AI
- Interruption handling for natural conversation
- Text fallback for chat mode
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.core.security import verify_access_token
from src.core.vad import (
    ConversationVADManager,
    VADConfig,
    VADBackend,
    RealtimeConversationSession,
)
from src.models.user import User
from src.models.assistant import Assistant
from src.models.avatar import Avatar
from src.models.conversation import Conversation
from src.models.response import Response as ResponseModel, ResponseItem

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/realtime", tags=["realtime"])


# Active sessions storage (in production, use Redis)
active_sessions: dict[str, "WebSocketSession"] = {}


class WebSocketSession:
    """Manages a WebSocket conversation session."""

    def __init__(
        self,
        websocket: WebSocket,
        user: User,
        assistant: Assistant,
        avatar: Avatar | None,
        db: AsyncSession,
    ):
        self.websocket = websocket
        self.user = user
        self.assistant = assistant
        self.avatar = avatar
        self.db = db

        self.session_id = str(uuid4())
        self.conversation_id: UUID | None = None
        self._latest_response_id: UUID | None = None

        # VAD configuration
        vad_config = VADConfig(
            backend=VADBackend.ENERGY,  # Use energy-based by default
            sample_rate=16000,
            frame_duration_ms=30,
            min_speech_duration_ms=250,
            max_silence_duration_ms=700,
            interruption_threshold_ms=200,
        )

        # Create conversation session
        self.conversation = RealtimeConversationSession(
            session_id=self.session_id,
            vad_config=vad_config,
        )

        # Set callbacks
        self.conversation.on_transcription = self._on_transcription
        self.conversation.on_response_start = self._on_response_start
        self.conversation.on_response_chunk = self._on_response_chunk
        self.conversation.on_response_end = self._on_response_end
        self.conversation.on_error = self._on_error

        # State
        self._is_active = False
        self._audio_queue: asyncio.Queue = asyncio.Queue()
        self._message_history: list[dict] = []

    async def start(self):
        """Start the session."""
        self._is_active = True
        await self.conversation.start()

        # Create or get conversation
        await self._init_conversation()

        # Send initial state
        await self._send_message({
            "type": "session_started",
            "data": {
                "session_id": self.session_id,
                "conversation_id": str(self.conversation_id),
                "assistant": {
                    "id": str(self.assistant.id),
                    "name": self.assistant.name,
                },
                "avatar": {
                    "id": str(self.avatar.id),
                    "name": self.avatar.name,
                    "type": self.avatar.avatar_type,
                } if self.avatar else None,
            }
        })

        # Send greeting if configured
        if self.avatar and self.avatar.greetings:
            import random
            greeting = random.choice(self.avatar.greetings)
            await self._send_message({
                "type": "greeting",
                "data": {
                    "text": greeting,
                }
            })

    async def stop(self):
        """Stop the session."""
        self._is_active = False
        await self.conversation.stop()

        # Clean up
        if self.session_id in active_sessions:
            del active_sessions[self.session_id]

    async def _init_conversation(self):
        """Initialize or retrieve conversation."""
        # Check for existing active conversation
        result = await self.db.execute(
            select(Conversation).where(
                Conversation.assistant_id == self.assistant.id,
                Conversation.user_id == self.user.id,
                Conversation.status == "active",
            ).order_by(Conversation.updated_at.desc()).limit(1)
        )
        conversation = result.scalar_one_or_none()

        if conversation:
            self.conversation_id = conversation.id
            self._latest_response_id = conversation.latest_response_id
            # Load recent response items
            result = await self.db.execute(
                select(ResponseItem)
                .join(ResponseModel, ResponseItem.response_id == ResponseModel.id)
                .where(ResponseModel.conversation_id == conversation.id)
                .where(ResponseItem.item_type == "message")
                .order_by(ResponseModel.created_at.desc(), ResponseItem.sequence_order.desc())
                .limit(20)
            )
            items = result.scalars().all()
            self._message_history = [
                {"role": item.role, "content": item.content}
                for item in reversed(items)
                if item.role and item.content
            ]
        else:
            # Create new conversation
            conversation = Conversation(
                assistant_id=self.assistant.id,
                user_id=self.user.id,
                title="Voice Conversation",
                metadata={
                    "mode": "realtime",
                    "avatar_id": str(self.avatar.id) if self.avatar else None,
                }
            )
            self.db.add(conversation)
            await self.db.flush()
            self.conversation_id = conversation.id
            self._latest_response_id = None

    async def handle_message(self, message: dict):
        """Handle incoming WebSocket message."""
        msg_type = message.get("type")

        if msg_type == "audio":
            # Decode base64 audio
            audio_data = base64.b64decode(message.get("data", ""))
            await self._handle_audio(audio_data)

        elif msg_type == "text":
            # Text input (chat mode)
            text = message.get("data", {}).get("text", "")
            await self._handle_text_input(text)

        elif msg_type == "interrupt":
            # Manual interrupt
            await self._handle_interrupt()

        elif msg_type == "config":
            # Update configuration
            await self._handle_config(message.get("data", {}))

        elif msg_type == "ping":
            await self._send_message({"type": "pong"})

    async def _handle_audio(self, audio_data: bytes):
        """Handle incoming audio chunk."""
        if not self._is_active:
            return

        # Process through VAD
        result = await self.conversation.process_audio_chunk(audio_data)

        if result:
            # Send VAD state to client
            await self._send_message({
                "type": "vad_state",
                "data": result,
            })

    async def _handle_text_input(self, text: str):
        """Handle text input (chat mode)."""
        if not text.strip():
            return

        # Save user message
        await self._save_message("user", text)

        # Notify transcription
        if self.conversation.on_transcription:
            await self.conversation.on_transcription(text)

    async def _handle_interrupt(self):
        """Handle manual interrupt request."""
        logger.info(f"Manual interrupt in session {self.session_id}")
        await self.conversation.vad_manager.set_ai_speaking(False)

        # Cancel any pending response
        if self.conversation._current_response_task:
            self.conversation._current_response_task.cancel()

        await self._send_message({
            "type": "interrupted",
            "data": {"reason": "manual"}
        })

    async def _handle_config(self, config: dict):
        """Handle configuration update."""
        # Update VAD sensitivity
        if "vad_sensitivity" in config:
            sensitivity = config["vad_sensitivity"]
            self.conversation.vad_manager.config.energy_threshold = 0.005 + (1 - sensitivity) * 0.02

        # Update interruption settings
        if "enable_interruption" in config:
            # Store setting (used in response generation)
            pass

        await self._send_message({
            "type": "config_updated",
            "data": config
        })

    async def _on_transcription(self, text: str):
        """Called when user speech is transcribed."""
        # Save user message
        await self._save_message("user", text)

        # Send to client
        await self._send_message({
            "type": "transcription",
            "data": {"text": text}
        })

    async def _on_response_start(self):
        """Called when AI starts responding."""
        await self._send_message({
            "type": "response_start",
            "data": {}
        })

    async def _on_response_chunk(self, text: str, audio: bytes):
        """Called for each chunk of AI response."""
        await self._send_message({
            "type": "response_chunk",
            "data": {
                "text": text,
                "audio": base64.b64encode(audio).decode() if audio else None,
            }
        })

    async def _on_response_end(self):
        """Called when AI finishes responding."""
        await self._send_message({
            "type": "response_end",
            "data": {}
        })

    async def _on_error(self, error: str):
        """Called on error."""
        await self._send_message({
            "type": "error",
            "data": {"message": error}
        })

    async def _save_message(self, role: str, content: str):
        """Save message as Response + ResponseItem to database."""
        direction = "input" if role == "user" else "output"

        response_record = ResponseModel(
            id=uuid4(),
            user_id=self.user.id,
            assistant_id=self.assistant.id,
            conversation_id=self.conversation_id,
            previous_response_id=self._latest_response_id,
            model=self.assistant.model,
            provider=self.assistant.provider,
            temperature=self.assistant.temperature or 0.7,
            max_tokens=self.assistant.max_tokens,
            status="completed",
            status_reason="stop",
            metadata={
                "mode": "realtime",
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        self.db.add(response_record)

        item = ResponseItem(
            id=uuid4(),
            response_id=response_record.id,
            sequence_order=0,
            item_type="message",
            direction=direction,
            role=role,
            content=content,
        )
        self.db.add(item)

        # Update conversation tracking
        self._latest_response_id = response_record.id

        # Update conversation's latest_response_id
        from sqlalchemy import update
        await self.db.execute(
            update(Conversation)
            .where(Conversation.id == self.conversation_id)
            .values(
                latest_response_id=response_record.id,
                response_count=Conversation.response_count + 1,
            )
        )

        await self.db.flush()

        # Update message history
        self._message_history.append({"role": role, "content": content})
        # Keep only last 20 messages
        if len(self._message_history) > 20:
            self._message_history = self._message_history[-20:]

    async def _send_message(self, message: dict):
        """Send message to WebSocket client."""
        try:
            await self.websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send WebSocket message: {e}")


async def authenticate_websocket(
    websocket: WebSocket,
    token: str,
    db: AsyncSession,
) -> User | None:
    """Authenticate WebSocket connection."""
    try:
        payload = verify_access_token(token)
        user_id = UUID(payload["sub"])

        user = await db.get(User, user_id)
        if not user or not user.is_active:
            return None

        return user
    except Exception as e:
        logger.error(f"WebSocket authentication failed: {e}")
        return None


@router.websocket("/conversation")
async def realtime_conversation(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
    assistant_id: str = Query(..., description="Assistant ID"),
    avatar_id: str | None = Query(None, description="Avatar ID (optional)"),
):
    """WebSocket endpoint for real-time voice conversation.

    Protocol:
    ---------
    Client -> Server:
    - {"type": "audio", "data": "<base64_encoded_audio>"}
    - {"type": "text", "data": {"text": "user message"}}
    - {"type": "interrupt"}
    - {"type": "config", "data": {...}}
    - {"type": "ping"}

    Server -> Client:
    - {"type": "session_started", "data": {...}}
    - {"type": "greeting", "data": {"text": "..."}}
    - {"type": "vad_state", "data": {"state": "...", "is_speech": bool}}
    - {"type": "transcription", "data": {"text": "..."}}
    - {"type": "response_start", "data": {}}
    - {"type": "response_chunk", "data": {"text": "...", "audio": "<base64>"}}
    - {"type": "response_end", "data": {}}
    - {"type": "interrupted", "data": {"reason": "..."}}
    - {"type": "error", "data": {"message": "..."}}
    - {"type": "pong"}
    """
    await websocket.accept()

    # Get database session
    async for db in get_db():
        try:
            # Authenticate
            user = await authenticate_websocket(websocket, token, db)
            if not user:
                await websocket.send_json({
                    "type": "error",
                    "data": {"message": "Authentication failed"}
                })
                await websocket.close(code=4001)
                return

            # Get assistant
            result = await db.execute(
                select(Assistant).where(
                    Assistant.id == UUID(assistant_id),
                )
            )
            assistant = result.scalar_one_or_none()

            if not assistant:
                await websocket.send_json({
                    "type": "error",
                    "data": {"message": "Assistant not found"}
                })
                await websocket.close(code=4004)
                return

            # Get avatar if specified
            avatar = None
            if avatar_id:
                result = await db.execute(
                    select(Avatar).where(Avatar.id == UUID(avatar_id))
                )
                avatar = result.scalar_one_or_none()

            # Create session
            session = WebSocketSession(
                websocket=websocket,
                user=user,
                assistant=assistant,
                avatar=avatar,
                db=db,
            )

            # Store session
            active_sessions[session.session_id] = session

            # Start session
            await session.start()

            # Handle messages
            try:
                while True:
                    data = await websocket.receive_json()
                    await session.handle_message(data)
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected: {session.session_id}")
            finally:
                await session.stop()

        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            try:
                await websocket.send_json({
                    "type": "error",
                    "data": {"message": str(e)}
                })
            except Exception:
                pass
        finally:
            try:
                await websocket.close()
            except Exception:
                pass
        break


@router.get("/sessions")
async def list_active_sessions():
    """List active real-time sessions."""
    return {
        "sessions": [
            {
                "session_id": s.session_id,
                "user_id": str(s.user.id),
                "assistant_id": str(s.assistant.id),
            }
            for s in active_sessions.values()
        ]
    }
