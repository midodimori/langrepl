"""Integration tests for server module HTTP helper functions.

These tests mock httpx responses to verify the HTTP helper functions
in src/cli/bootstrap/server.py work correctly under various conditions.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.cli.bootstrap.server import (
    _get_or_create_thread,
    _send_message,
    _upsert_assistant,
    _wait_for_server_ready,
    generate_langgraph_json,
)


def make_response(status_code: int, json_data=None):
    """Create a mock httpx Response with synchronous methods."""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data
    response.raise_for_status = MagicMock()
    return response


class TestGenerateLanggraphJson:
    """Tests for langgraph.json configuration file generation."""

    def test_generates_basic_config(self, temp_dir):
        """Generate config without .env file."""
        generate_langgraph_json(temp_dir)

        config_path = temp_dir / ".langrepl" / "langgraph.json"
        assert config_path.exists()

        config = json.loads(config_path.read_text())
        assert "dependencies" in config
        assert "graphs" in config
        assert config["graphs"]["agent"] == "src/cli/bootstrap/server.py:get_graph"
        assert "env" not in config

    def test_includes_env_when_present(self, temp_dir):
        """Include env reference when .env file exists."""
        (temp_dir / ".env").write_text("API_KEY=test")

        generate_langgraph_json(temp_dir)

        config_path = temp_dir / ".langrepl" / "langgraph.json"
        config = json.loads(config_path.read_text())
        assert config["env"] == ".env"


class TestWaitForServerReady:
    """Tests for server readiness polling."""

    @pytest.mark.asyncio
    async def test_returns_true_when_server_ready(self):
        """Return True when server responds with 200 OK."""
        mock_response = make_response(200)

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        result = await _wait_for_server_ready(
            mock_client, "http://localhost:8123", timeout_seconds=1
        )

        assert result is True
        mock_client.get.assert_awaited_with("http://localhost:8123/ok")

    @pytest.mark.asyncio
    async def test_returns_false_on_timeout(self):
        """Return False when server doesn't respond within timeout."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.HTTPError("Connection refused"))

        with patch("src.cli.bootstrap.server.asyncio.sleep", new_callable=AsyncMock):
            result = await _wait_for_server_ready(
                mock_client, "http://localhost:8123", timeout_seconds=1
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_retries_on_http_error(self):
        """Retry on HTTP errors until success."""
        mock_response = make_response(200)

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        # Fail twice, then succeed
        mock_client.get = AsyncMock(
            side_effect=[
                httpx.HTTPError("Connection refused"),
                httpx.HTTPError("Connection refused"),
                mock_response,
            ]
        )

        with patch("src.cli.bootstrap.server.asyncio.sleep", new_callable=AsyncMock):
            result = await _wait_for_server_ready(
                mock_client, "http://localhost:8123", timeout_seconds=5
            )

        assert result is True
        assert mock_client.get.await_count == 3


class TestUpsertAssistant:
    """Tests for assistant creation/update logic."""

    @pytest.mark.asyncio
    async def test_creates_new_assistant(self):
        """Create new assistant when none exists."""
        # Empty search response (no existing assistant)
        search_response = make_response(200, [])

        # Create response
        create_response = make_response(
            200, {"assistant_id": "new-id", "name": "Test", "version": 1}
        )

        # Version response
        version_response = make_response(200)

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(
            side_effect=[search_response, create_response, version_response]
        )

        assistant, was_updated = await _upsert_assistant(
            mock_client,
            "http://localhost:8123",
            "Test",
            {"graph_id": "agent", "name": "Test"},
        )

        assert assistant is not None
        assert assistant["assistant_id"] == "new-id"
        assert was_updated is False

    @pytest.mark.asyncio
    async def test_updates_existing_assistant(self):
        """Update existing assistant when found."""
        # Search finds existing assistant
        search_response = make_response(200, [{"assistant_id": "existing-id"}])

        # Patch response
        patch_response = make_response(
            200, {"assistant_id": "existing-id", "name": "Test", "version": 2}
        )

        # Version response
        version_response = make_response(200)

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(side_effect=[search_response, version_response])
        mock_client.patch = AsyncMock(return_value=patch_response)

        assistant, was_updated = await _upsert_assistant(
            mock_client,
            "http://localhost:8123",
            "Test",
            {"graph_id": "agent", "name": "Test"},
        )

        assert assistant is not None
        assert assistant["version"] == 2
        assert was_updated is True


class TestGetOrCreateThread:
    """Tests for thread retrieval/creation logic."""

    @pytest.mark.asyncio
    async def test_resumes_existing_thread(self):
        """Resume last thread when resume=True and threads exist."""
        search_response = make_response(200, [{"thread_id": "existing-thread-123"}])

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=search_response)

        thread_id = await _get_or_create_thread(
            mock_client, "http://localhost:8123", resume=True
        )

        assert thread_id == "existing-thread-123"

    @pytest.mark.asyncio
    async def test_creates_new_thread_when_no_resume(self):
        """Create new thread when resume=False."""
        create_response = make_response(200, {"thread_id": "new-thread-456"})

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=create_response)

        thread_id = await _get_or_create_thread(
            mock_client, "http://localhost:8123", resume=False
        )

        assert thread_id == "new-thread-456"
        mock_client.post.assert_awaited_with("http://localhost:8123/threads", json={})

    @pytest.mark.asyncio
    async def test_creates_new_thread_when_resume_but_no_threads(self):
        """Create new thread when resume=True but no threads exist."""
        # Empty search result
        search_response = make_response(200, [])

        # Create response
        create_response = make_response(200, {"thread_id": "fallback-thread"})

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(side_effect=[search_response, create_response])

        thread_id = await _get_or_create_thread(
            mock_client, "http://localhost:8123", resume=True
        )

        assert thread_id == "fallback-thread"


class TestSendMessage:
    """Tests for message sending functionality."""

    @pytest.mark.asyncio
    async def test_sends_message_successfully(self):
        """Send message and return success."""
        # Thread create response
        thread_response = make_response(200, {"thread_id": "test-thread"})

        # Run response
        run_response = make_response(200)

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(side_effect=[thread_response, run_response])

        exit_code, thread_id = await _send_message(
            mock_client,
            "http://localhost:8123",
            "assistant-id",
            "Hello, world!",
            resume=False,
        )

        assert exit_code == 0
        assert thread_id == "test-thread"

    @pytest.mark.asyncio
    async def test_returns_error_on_failure(self):
        """Return error code on HTTP failure."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(side_effect=httpx.HTTPError("Server error"))

        exit_code, thread_id = await _send_message(
            mock_client,
            "http://localhost:8123",
            "assistant-id",
            "Hello",
            resume=False,
        )

        assert exit_code == 1
        assert thread_id == ""
