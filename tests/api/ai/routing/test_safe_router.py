import pytest
import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch
from theo.infrastructure.api.app.research.ai.routing.router import SafeAIRouter
from theo.infrastructure.api.app.research.ai.cache.cache_manager import CacheManager
from theo.infrastructure.api.app.research.ai import BaseAIClient, AIProvider

class MockClient(BaseAIClient):
    def __init__(self, provider: AIProvider, model: str, response: str = "response"):
        self._provider = provider
        self._model = model
        self.response = response
        self.fail = False
        self.call_count = 0

    async def complete(self, prompt: str, **kwargs) -> str:
        self.call_count += 1
        if self.fail:
            raise RuntimeError(f"Client {self._model} failed")
        return self.response

    async def stream(self, prompt: str, **kwargs):
        yield self.response

    def get_provider(self) -> AIProvider:
        return self._provider

    def get_model_name(self) -> str:
        return self._model

@pytest.mark.asyncio
async def test_safe_router_basic_flow():
    client = MockClient(AIProvider.OPENAI, "gpt-4")
    router = SafeAIRouter(clients=[client])

    result = await router.execute_generation(prompt="hello")
    assert result == "response"
    assert client.call_count == 1

@pytest.mark.asyncio
@pytest.mark.allow_sleep
async def test_safe_router_deduplication():
    client = MockClient(AIProvider.OPENAI, "gpt-4")
    # Simulate slow client
    async def slow_complete(prompt, **kwargs):
        client.call_count += 1
        await asyncio.sleep(0.1)
        return "slow_response"
    client.complete = slow_complete

    router = SafeAIRouter(clients=[client])

    # Launch 3 concurrent requests
    tasks = [
        router.execute_generation(prompt="same"),
        router.execute_generation(prompt="same"),
        router.execute_generation(prompt="same")
    ]

    results = await asyncio.gather(*tasks)

    assert results == ["slow_response", "slow_response", "slow_response"]
    # Should only be called once due to deduplication
    assert client.call_count == 1

@pytest.mark.asyncio
async def test_safe_router_fallback():
    client1 = MockClient(AIProvider.OPENAI, "gpt-4")
    client1.fail = True

    client2 = MockClient(AIProvider.ANTHROPIC, "claude-3")
    client2.response = "fallback_response"

    router = SafeAIRouter(clients=[client1, client2])

    result = await router.execute_generation(prompt="hello")
    assert result == "fallback_response"
    assert client1.call_count == 1
    assert client2.call_count == 1

@pytest.mark.asyncio
async def test_safe_router_caching():
    client = MockClient(AIProvider.OPENAI, "gpt-4")
    cache = CacheManager()
    router = SafeAIRouter(clients=[client], cache_manager=cache)

    # First call
    result1 = await router.execute_generation(prompt="cache_test")
    assert result1 == "response"
    assert client.call_count == 1

    # Second call should hit cache
    result2 = await router.execute_generation(prompt="cache_test")
    assert result2 == "response"
    assert client.call_count == 1  # Count stays 1

@pytest.mark.asyncio
@pytest.mark.allow_sleep
async def test_cache_manager_ttl():
    cache = CacheManager(default_ttl=timedelta(seconds=0.1))
    await cache.set("key", "value")

    assert await cache.get("key") == "value"

    await asyncio.sleep(0.2)
    assert await cache.get("key") is None

@pytest.mark.asyncio
async def test_safe_router_all_fail():
    client = MockClient(AIProvider.OPENAI, "gpt-4")
    client.fail = True
    router = SafeAIRouter(clients=[client])

    with pytest.raises(RuntimeError, match="All AI clients failed"):
        await router.execute_generation(prompt="hello")
