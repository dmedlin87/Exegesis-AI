"""Local AI client implementation (e.g. Ollama, vLLM)."""
from __future__ import annotations

from typing import Any, AsyncIterator, Dict, Optional

from .. import AIProvider, BaseAIClient

try:  # pragma: no cover - import guarded for optional dependency
    import openai
except ModuleNotFoundError:  # pragma: no cover - handled at runtime
    openai = None  # type: ignore


class LocalAIClient(BaseAIClient):
    """Asynchronous client for local AI providers (Ollama, vLLM) using OpenAI-compatible API."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        model: str = "llama3",
        api_key: str = "ollama",  # Many local servers require non-empty key
        extra_client_kwargs: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.base_url = base_url
        self.model = model
        self.api_key = api_key
        self.extra_client_kwargs = extra_client_kwargs or {}
        self._client: Optional["openai.AsyncOpenAI"] = None

    @property
    def client(self) -> "openai.AsyncOpenAI":
        """Lazily instantiate the OpenAI client pointing to local server."""

        if openai is None:  # pragma: no cover - defensive guard
            raise RuntimeError("openai package is not installed")

        if self._client is None:
            kwargs: Dict[str, Any] = {
                "api_key": self.api_key,
                "base_url": self.base_url,
                **self.extra_client_kwargs
            }
            self._client = openai.AsyncOpenAI(**kwargs)
        return self._client

    async def complete(self, prompt: str, **kwargs: Any) -> str:
        """Generate a completion using the configured local model."""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            **kwargs,
        )
        return response.choices[0].message.content or ""

    async def stream(self, prompt: str, **kwargs: Any) -> AsyncIterator[str]:
        """Stream a completion response as tokens arrive."""

        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            **kwargs,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            content = getattr(delta, "content", None)
            if content:
                yield content

    def get_provider(self) -> AIProvider:
        return AIProvider.LOCAL

    def get_model_name(self) -> str:
        return self.model


__all__ = ["LocalAIClient"]
