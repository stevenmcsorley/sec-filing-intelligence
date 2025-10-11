"""Thin HTTP client for Groq chat completions."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import httpx

ChatRole = Literal["system", "user", "assistant"]


@dataclass(slots=True)
class ChatMessage:
    """Single chat message for Groq completion calls."""

    role: ChatRole
    content: str


@dataclass(slots=True)
class ChatCompletionResult:
    """Normalized result from Groq chat completions."""

    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class GroqChatClient:
    """Wrapper around Groq's OpenAI-compatible chat completions endpoint."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str,
        timeout: float,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def chat_completion(
        self,
        *,
        model: str,
        messages: Sequence[ChatMessage],
        max_tokens: int,
        temperature: float,
    ) -> ChatCompletionResult:
        payload = {
            "model": model,
            "messages": [
                {"role": message.role, "content": message.content} for message in messages
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        response = await self._client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("Groq response missing choices")
        message = choices[0].get("message") or {}
        content = str(message.get("content", "")).strip()
        usage = data.get("usage") or {}
        return ChatCompletionResult(
            content=content,
            model=str(data.get("model", model)),
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            total_tokens=int(usage.get("total_tokens") or 0),
        )
