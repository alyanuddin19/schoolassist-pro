"""Alibaba Model Studio / Qwen client using the OpenAI-compatible API."""

import json
import re

from openai import OpenAI

from ..core.config import settings


class QwenNotConfiguredError(RuntimeError):
    pass


class QwenClient:
    """Thin wrapper around the OpenAI-compatible DashScope endpoint.

    Endpoint style (OpenAI compatible):
        POST {QWEN_BASE_URL}/chat/completions  with Authorization: Bearer {DASHSCOPE_API_KEY}
    """

    def __init__(self) -> None:
        self._client: OpenAI | None = None

    @property
    def configured(self) -> bool:
        return bool(settings.DASHSCOPE_API_KEY)

    @property
    def model(self) -> str:
        return settings.QWEN_MODEL

    def _get_client(self) -> OpenAI:
        if not self.configured:
            raise QwenNotConfiguredError(
                "Qwen API is not configured. Set DASHSCOPE_API_KEY in the backend .env file."
            )
        if self._client is None:
            self._client = OpenAI(
                api_key=settings.DASHSCOPE_API_KEY,
                base_url=settings.QWEN_BASE_URL,
            )
        return self._client

    def chat(
        self,
        messages: list,
        temperature: float = 0.4,
        max_tokens: int = 3000,
        json_mode: bool = False,
    ) -> str:
        client = self._get_client()
        kwargs: dict = {
            "model": settings.QWEN_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            response = client.chat.completions.create(**kwargs)
        except Exception:
            if json_mode:
                # Some models/regional endpoints reject response_format: retry without it
                kwargs.pop("response_format", None)
                response = client.chat.completions.create(**kwargs)
            else:
                raise
        return (response.choices[0].message.content or "").strip()

    def chat_json(
        self,
        messages: list,
        temperature: float = 0.2,
        max_tokens: int = 3000,
    ) -> dict:
        raw = self.chat(messages, temperature=temperature, max_tokens=max_tokens, json_mode=True)
        return parse_json_loose(raw)


def parse_json_loose(raw: str) -> dict:
    """Best-effort JSON extraction from an LLM reply (handles ```json fences)."""
    if not raw:
        return {}
    cleaned = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end > start:
        cleaned = cleaned[start : end + 1]
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


_client: QwenClient | None = None


def get_qwen_client() -> QwenClient:
    global _client
    if _client is None:
        _client = QwenClient()
    return _client
