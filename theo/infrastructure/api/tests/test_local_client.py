"""Tests for the Local AI client."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from theo.infrastructure.api.app.research.ai import AIProvider
from theo.infrastructure.api.app.research.ai.clients.local_client import LocalAIClient


@pytest.fixture
def mock_openai():
    with patch("theo.infrastructure.api.app.research.ai.clients.local_client.openai") as mock:
        yield mock


@pytest.mark.asyncio
async def test_local_client_initialization(mock_openai):
    client = LocalAIClient(base_url="http://test:1234", model="test-model")
    assert client.get_provider() == AIProvider.LOCAL
    assert client.get_model_name() == "test-model"

    # Verify lazy initialization
    assert client._client is None
    _ = client.client
    assert client._client is not None

    mock_openai.AsyncOpenAI.assert_called_once_with(
        api_key="ollama",
        base_url="http://test:1234"
    )


@pytest.mark.asyncio
async def test_local_client_complete(mock_openai):
    client = LocalAIClient()

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="Test response"))]

    mock_openai.AsyncOpenAI.return_value.chat.completions.create = AsyncMock(
        return_value=mock_response
    )

    response = await client.complete("Hello")
    assert response == "Test response"

    mock_openai.AsyncOpenAI.return_value.chat.completions.create.assert_called_once_with(
        model="llama3",
        messages=[{"role": "user", "content": "Hello"}]
    )


@pytest.mark.asyncio
async def test_local_client_stream(mock_openai):
    client = LocalAIClient()

    mock_chunk = MagicMock()
    mock_chunk.choices = [MagicMock(delta=MagicMock(content="Chunk"))]

    async def mock_stream():
        yield mock_chunk

    mock_openai.AsyncOpenAI.return_value.chat.completions.create = AsyncMock(
        return_value=mock_stream()
    )

    chunks = []
    async for chunk in client.stream("Hello"):
        chunks.append(chunk)

    assert chunks == ["Chunk"]

    mock_openai.AsyncOpenAI.return_value.chat.completions.create.assert_called_once_with(
        model="llama3",
        messages=[{"role": "user", "content": "Hello"}],
        stream=True
    )
