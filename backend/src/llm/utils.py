"""LLM Provider Utilities - Reusable helpers for provider implementations.

This module provides utility functions and classes that eliminate code
duplication across LLM provider implementations.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from src.llm.providers.base import (
    Message,
    StreamDelta,
    ToolCall,
)


class StreamingToolCallProcessor:
    """Processes streaming tool call deltas into complete ToolCall objects.

    This class eliminates the duplicated tool call accumulation logic
    found across multiple LLM providers.

    Example:
        processor = StreamingToolCallProcessor()

        async for chunk in stream:
            delta = chunk.choices[0].delta

            if delta.content:
                yield StreamDelta(type="text", content=delta.content)

            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    processor.process_delta(tc_delta)

            if chunk.choices[0].finish_reason:
                for tool_call in processor.get_completed_calls():
                    yield StreamDelta(type="tool_call", tool_call=tool_call)
                yield StreamDelta(type="finish", finish_reason=chunk.choices[0].finish_reason)
    """

    def __init__(self):
        self._current_calls: dict[int, dict[str, Any]] = {}

    def process_delta(self, tc_delta: Any) -> None:
        """Process a single tool call delta from the stream.

        Args:
            tc_delta: Tool call delta object with index, id, and function attributes
        """
        idx = getattr(tc_delta, "index", 0)

        if idx not in self._current_calls:
            self._current_calls[idx] = {
                "id": getattr(tc_delta, "id", "") or "",
                "type": "function",
                "function": {"name": "", "arguments": ""},
            }

        if getattr(tc_delta, "id", None):
            self._current_calls[idx]["id"] = tc_delta.id

        if hasattr(tc_delta, "function") and tc_delta.function:
            func = tc_delta.function
            if getattr(func, "name", None):
                self._current_calls[idx]["function"]["name"] = func.name
            if getattr(func, "arguments", None):
                self._current_calls[idx]["function"]["arguments"] += func.arguments

    def get_completed_calls(self) -> list[ToolCall]:
        """Get all completed tool calls and reset state.

        Returns:
            List of ToolCall objects
        """
        calls = [
            ToolCall(**tc_data)
            for tc_data in self._current_calls.values()
            if tc_data["function"]["name"]  # Only include calls with a name
        ]
        self._current_calls.clear()
        return calls

    def reset(self) -> None:
        """Reset the processor state."""
        self._current_calls.clear()


class MessageFormatter:
    """Formats messages for different API formats.

    Provides reusable message formatting logic that can be customized
    for different provider requirements.
    """

    @staticmethod
    def to_openai_format(messages: list[Message]) -> list[dict[str, Any]]:
        """Format messages for OpenAI-compatible APIs.

        Used by: OpenAI, Azure OpenAI, Groq, Fireworks, Together
        """
        formatted = []

        for msg in messages:
            formatted_msg: dict[str, Any] = {
                "role": msg.role,
                "content": msg.content,
            }

            if msg.name:
                formatted_msg["name"] = msg.name

            if msg.tool_calls:
                formatted_msg["tool_calls"] = msg.tool_calls

            if msg.tool_call_id:
                formatted_msg["tool_call_id"] = msg.tool_call_id

            formatted.append(formatted_msg)

        return formatted

    @staticmethod
    def to_anthropic_format(
        messages: list[Message],
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """Format messages for Anthropic Claude API.

        Returns:
            Tuple of (system_prompt, formatted_messages)
        """
        system_prompt = None
        formatted = []

        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content
                continue

            if msg.role == "tool":
                formatted.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.tool_call_id,
                            "content": msg.content,
                        }
                    ],
                })
            elif msg.role == "assistant" and msg.tool_calls:
                content: list[dict[str, Any]] = []
                if msg.content:
                    content.append({"type": "text", "text": msg.content})
                for tc in msg.tool_calls:
                    content.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["function"]["name"],
                        "input": tc["function"].get("arguments", {}),
                    })
                formatted.append({"role": "assistant", "content": content})
            else:
                formatted.append({
                    "role": msg.role,
                    "content": msg.content,
                })

        return system_prompt, formatted

    @staticmethod
    def to_google_format(messages: list[Message]) -> tuple[str | None, list[dict[str, Any]]]:
        """Format messages for Google Gemini API.

        Returns:
            Tuple of (system_instruction, formatted_contents)
        """
        system_instruction = None
        contents = []

        for msg in messages:
            if msg.role == "system":
                system_instruction = msg.content
                continue

            role = "user" if msg.role == "user" else "model"

            parts: list[dict[str, Any]] = []
            if msg.content:
                parts.append({"text": msg.content})

            if msg.tool_calls:
                for tc in msg.tool_calls:
                    import json
                    args = tc["function"].get("arguments", "{}")
                    if isinstance(args, str):
                        args = json.loads(args)
                    parts.append({
                        "functionCall": {
                            "name": tc["function"]["name"],
                            "args": args,
                        }
                    })

            if msg.role == "tool":
                parts = [{
                    "functionResponse": {
                        "name": msg.name or "function",
                        "response": {"result": msg.content},
                    }
                }]
                role = "function"

            contents.append({"role": role, "parts": parts})

        return system_instruction, contents

    @staticmethod
    def to_cohere_format(
        messages: list[Message],
    ) -> tuple[str | None, list[dict[str, Any]], str]:
        """Format messages for Cohere API.

        Returns:
            Tuple of (preamble, chat_history, current_message)
        """
        preamble = None
        chat_history = []
        current_message = ""

        # Extract system/preamble
        non_system = []
        for msg in messages:
            if msg.role == "system":
                preamble = msg.content
            else:
                non_system.append(msg)

        # Last user message is current message
        for i, msg in enumerate(non_system):
            if i == len(non_system) - 1 and msg.role == "user":
                current_message = msg.content
            else:
                role = "USER" if msg.role == "user" else "CHATBOT"

                if msg.role == "tool":
                    chat_history.append({
                        "role": "TOOL",
                        "tool_results": [{
                            "call": {"name": msg.name or "function"},
                            "outputs": [{"result": msg.content}],
                        }],
                    })
                else:
                    chat_history.append({
                        "role": role,
                        "message": msg.content,
                    })

        return preamble, chat_history, current_message


async def process_openai_compatible_stream(
    stream: AsyncGenerator[Any, None],
    processor: StreamingToolCallProcessor | None = None,
) -> AsyncGenerator[StreamDelta, None]:
    """Process an OpenAI-compatible streaming response.

    This generator handles the common streaming pattern used by
    OpenAI, Azure OpenAI, Groq, Fireworks, Together, and others.
    """
    if processor is None:
        processor = StreamingToolCallProcessor()

    async for chunk in stream:
        if not chunk.choices:
            continue

        choice = chunk.choices[0]
        delta = choice.delta

        # Handle text content
        if delta.content:
            yield StreamDelta(type="text", content=delta.content)

        # Handle tool calls
        if hasattr(delta, "tool_calls") and delta.tool_calls:
            for tc_delta in delta.tool_calls:
                processor.process_delta(tc_delta)

        # Handle finish
        if choice.finish_reason:
            # Yield accumulated tool calls
            for tool_call in processor.get_completed_calls():
                yield StreamDelta(type="tool_call", tool_call=tool_call)

            # Get usage if available
            input_tokens = None
            output_tokens = None
            if hasattr(chunk, "usage") and chunk.usage:
                input_tokens = getattr(chunk.usage, "prompt_tokens", None)
                output_tokens = getattr(chunk.usage, "completion_tokens", None)

            yield StreamDelta(
                type="finish",
                finish_reason=choice.finish_reason,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )


def extract_tool_calls_from_response(message: Any) -> list[ToolCall] | None:
    """Extract tool calls from an OpenAI-compatible response message.

    Works with OpenAI, Azure OpenAI, Groq, Mistral, etc.
    """
    if not hasattr(message, "tool_calls") or not message.tool_calls:
        return None

    return [
        ToolCall(
            id=tc.id,
            type=getattr(tc, "type", "function"),
            function={
                "name": tc.function.name,
                "arguments": tc.function.arguments,
            },
        )
        for tc in message.tool_calls
    ]
