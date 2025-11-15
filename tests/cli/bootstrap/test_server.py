"""Tests for server command handler."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.cli.bootstrap.server import (
    _set_assistant_version,
    _upsert_assistant,
    _wait_for_server_ready,
    generate_langgraph_json,
    get_graph,
    handle_server_command,
)
from src.core.constants import CONFIG_LANGGRAPH_FILE_NAME


@pytest.fixture
def mock_http_client():
    """Create a mock HTTP client for server tests."""
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(
        return_value={"assistant_id": "test-id", "version": 1, "name": "Test"}
    )
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.post = AsyncMock(
        return_value=MagicMock(status_code=200, json=MagicMock(return_value=[]))
    )
    return mock_client


@pytest.fixture
def mock_subprocess():
    """Create a mock subprocess for server tests."""
    mock_process = MagicMock()
    mock_process.wait = MagicMock(return_value=0)
    return mock_process


@pytest.fixture
def patch_get_graph(mock_initializer):
    """Patch initializer for get_graph tests."""
    with patch("src.cli.bootstrap.server.initializer", mock_initializer):
        yield mock_initializer


@pytest.fixture
def patch_server_dependencies(
    mock_initializer,
    mock_agent_config,
    mock_llm_config,
    mock_http_client,
    mock_subprocess,
):
    """Patch dependencies for handle_server_command tests."""
    mock_agent_config.llm = mock_llm_config

    with (
        patch("src.cli.bootstrap.server.initializer", mock_initializer),
        patch(
            "src.cli.bootstrap.server.subprocess.Popen", return_value=mock_subprocess
        ) as mock_popen,
        patch("src.cli.bootstrap.server.httpx.AsyncClient") as mock_client_cls,
    ):
        mock_client_cls.return_value.__aenter__ = AsyncMock(
            return_value=mock_http_client
        )
        mock_client_cls.return_value.__aexit__ = AsyncMock()

        yield {
            "initializer": mock_initializer,
            "agent_config": mock_agent_config,
            "llm_config": mock_llm_config,
            "popen": mock_popen,
            "client_cls": mock_client_cls,
            "client": mock_http_client,
            "process": mock_subprocess,
        }


class TestGenerateLanggraphJson:
    """Tests for generate_langgraph_json function."""

    def test_generate_langgraph_json_creates_file(self, temp_dir):
        """Test that generate_langgraph_json creates langgraph.json."""
        generate_langgraph_json(temp_dir)

        langgraph_json_path = temp_dir / CONFIG_LANGGRAPH_FILE_NAME
        assert langgraph_json_path.exists()

    def test_generate_langgraph_json_has_correct_structure(self, temp_dir):
        """Test that generated langgraph.json has correct structure."""
        generate_langgraph_json(temp_dir)

        langgraph_json_path = temp_dir / CONFIG_LANGGRAPH_FILE_NAME
        with open(langgraph_json_path) as f:
            config = json.load(f)

        assert "dependencies" in config
        assert "graphs" in config
        assert "agent" in config["graphs"]
        assert config["graphs"]["agent"] == "src/cli/bootstrap/server.py:get_graph"

    def test_generate_langgraph_json_includes_env_when_exists(self, temp_dir):
        """Test that .env is included in config when it exists."""
        env_file = temp_dir / ".env"
        env_file.write_text("TEST=value")

        generate_langgraph_json(temp_dir)

        langgraph_json_path = temp_dir / CONFIG_LANGGRAPH_FILE_NAME
        with open(langgraph_json_path) as f:
            config = json.load(f)

        assert "env" in config
        assert config["env"] == ".env"

    def test_generate_langgraph_json_excludes_env_when_missing(self, temp_dir):
        """Test that .env is excluded from config when it doesn't exist."""
        generate_langgraph_json(temp_dir)

        langgraph_json_path = temp_dir / CONFIG_LANGGRAPH_FILE_NAME
        with open(langgraph_json_path) as f:
            config = json.load(f)

        assert "env" not in config

    def test_generate_langgraph_json_creates_parent_dir(self, temp_dir):
        """Test that parent directory is created if it doesn't exist."""
        config_dir = temp_dir / CONFIG_LANGGRAPH_FILE_NAME.parent
        assert not config_dir.exists()

        generate_langgraph_json(temp_dir)

        assert config_dir.exists()
        assert config_dir.is_dir()


class TestGetGraph:
    """Tests for get_graph function."""

    @pytest.mark.asyncio
    async def test_get_graph_reads_env_variables(
        self, temp_dir, monkeypatch, patch_get_graph, mock_graph
    ):
        """Test that get_graph reads environment variables."""
        monkeypatch.setenv("LANGREPL_AGENT", "test-agent")
        monkeypatch.setenv("LANGREPL_MODEL", "test-model")
        monkeypatch.setenv("LANGREPL_WORKING_DIR", str(temp_dir))

        result = await get_graph()

        assert result == mock_graph

    @pytest.mark.asyncio
    async def test_get_graph_requires_working_dir(self, monkeypatch):
        """Test that get_graph raises ValueError when LANGREPL_WORKING_DIR is missing."""
        monkeypatch.delenv("LANGREPL_WORKING_DIR", raising=False)

        with pytest.raises(ValueError, match="LANGREPL_WORKING_DIR"):
            await get_graph()

    @pytest.mark.asyncio
    async def test_get_graph_handles_missing_agent(
        self, temp_dir, monkeypatch, patch_get_graph, mock_graph
    ):
        """Test that get_graph handles missing LANGREPL_AGENT."""
        monkeypatch.delenv("LANGREPL_AGENT", raising=False)
        monkeypatch.setenv("LANGREPL_WORKING_DIR", str(temp_dir))

        result = await get_graph()

        assert result == mock_graph

    @pytest.mark.asyncio
    async def test_get_graph_handles_missing_model(
        self, temp_dir, monkeypatch, patch_get_graph, mock_graph
    ):
        """Test that get_graph handles missing LANGREPL_MODEL."""
        monkeypatch.setenv("LANGREPL_AGENT", "test-agent")
        monkeypatch.delenv("LANGREPL_MODEL", raising=False)
        monkeypatch.setenv("LANGREPL_WORKING_DIR", str(temp_dir))

        result = await get_graph()

        assert result == mock_graph


class TestWaitForServerReady:
    """Tests for _wait_for_server_ready function."""

    @pytest.mark.asyncio
    async def test_wait_for_server_ready_returns_true_on_success(self):
        """Test that _wait_for_server_ready returns True when server is ready."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.get = AsyncMock(return_value=mock_response)

        result = await _wait_for_server_ready(
            mock_client, "http://localhost:8000", timeout_seconds=1
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_wait_for_server_ready_returns_false_on_timeout(self):
        """Test that _wait_for_server_ready returns False on timeout."""
        import httpx

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.HTTPError("Connection refused"))

        result = await _wait_for_server_ready(
            mock_client, "http://localhost:8000", timeout_seconds=1
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_wait_for_server_ready_retries_on_failure(self):
        """Test that _wait_for_server_ready retries on failure."""
        mock_client = AsyncMock()
        mock_response_fail = MagicMock()
        mock_response_fail.status_code = 500
        mock_response_success = MagicMock()
        mock_response_success.status_code = 200

        mock_client.get = AsyncMock(
            side_effect=[mock_response_fail, mock_response_success]
        )

        result = await _wait_for_server_ready(
            mock_client, "http://localhost:8000", timeout_seconds=2
        )

        assert result is True
        assert mock_client.get.call_count == 2


class TestSetAssistantVersion:
    """Tests for _set_assistant_version function."""

    @pytest.mark.asyncio
    async def test_set_assistant_version_makes_post_request(self):
        """Test that _set_assistant_version makes POST request."""
        mock_client = AsyncMock()
        assistant = {"assistant_id": "test-id", "version": 1}

        await _set_assistant_version(mock_client, "http://localhost:8000", assistant)

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "test-id" in call_args[0][0]
        assert call_args[1]["json"]["version"] == 1


class TestUpsertAssistant:
    """Tests for _upsert_assistant function."""

    @pytest.mark.asyncio
    @patch("src.cli.bootstrap.server._set_assistant_version", new_callable=AsyncMock)
    async def test_upsert_assistant_creates_new_assistant(
        self,
        _mock_set_version,
    ):
        """Test that _upsert_assistant creates new assistant when none exists."""
        mock_client = AsyncMock()

        mock_search_response = MagicMock()
        mock_search_response.status_code = 200
        mock_search_response.json = MagicMock(return_value=[])

        mock_create_response = MagicMock()
        mock_create_response.status_code = 200
        mock_create_response.json = MagicMock(
            return_value={"assistant_id": "new-id", "version": 1}
        )

        post_calls = [mock_search_response, mock_create_response]

        async def mock_post(*args, **kwargs):
            return post_calls.pop(0)

        mock_client.post = mock_post

        assistant, was_updated = await _upsert_assistant(
            mock_client, "http://localhost:8000", "Test Assistant", {}
        )

        assert assistant is not None
        assert was_updated is False
        assert assistant["assistant_id"] == "new-id"

    @pytest.mark.asyncio
    async def test_upsert_assistant_updates_existing_assistant(self):
        """Test that _upsert_assistant updates existing assistant."""
        mock_client = AsyncMock()

        mock_search_response = MagicMock()
        mock_search_response.status_code = 200
        mock_search_response.json = MagicMock(
            return_value=[{"assistant_id": "existing-id"}]
        )

        mock_update_response = MagicMock()
        mock_update_response.status_code = 200
        mock_update_response.json = MagicMock(
            return_value={"assistant_id": "existing-id", "version": 2}
        )

        mock_client.post = AsyncMock(return_value=mock_search_response)
        mock_client.patch = AsyncMock(return_value=mock_update_response)

        assistant, was_updated = await _upsert_assistant(
            mock_client, "http://localhost:8000", "Test Assistant", {}
        )

        assert assistant is not None
        assert was_updated is True
        assert assistant["assistant_id"] == "existing-id"

    @pytest.mark.asyncio
    async def test_upsert_assistant_handles_failure(self):
        """Test that _upsert_assistant handles failure gracefully."""
        import httpx

        mock_client = AsyncMock()

        async def mock_post(*args, **kwargs):
            raise httpx.HTTPError("Network error")

        mock_client.post = mock_post

        assistant, was_updated = await _upsert_assistant(
            mock_client, "http://localhost:8000", "Test Assistant", {}
        )

        assert assistant is None
        assert was_updated is False


class TestHandleServerCommand:
    """Tests for handle_server_command function."""

    @pytest.mark.asyncio
    async def test_handle_server_command_generates_config(
        self, mock_app_args, patch_server_dependencies
    ):
        """Test that handle_server_command generates langgraph.json."""
        await handle_server_command(mock_app_args)

        langgraph_json_path = (
            Path(mock_app_args.working_dir) / CONFIG_LANGGRAPH_FILE_NAME
        )
        assert langgraph_json_path.exists()

    @pytest.mark.asyncio
    async def test_handle_server_command_starts_subprocess(
        self, mock_app_args, patch_server_dependencies
    ):
        """Test that handle_server_command starts langgraph dev subprocess."""
        await handle_server_command(mock_app_args)

        patch_server_dependencies["popen"].assert_called_once()
        call_args = patch_server_dependencies["popen"].call_args[0][0]
        assert any("langgraph" in str(arg) for arg in call_args)
        assert "dev" in call_args

    @pytest.mark.asyncio
    async def test_handle_server_command_sets_env_variables(
        self, mock_app_args, patch_server_dependencies
    ):
        """Test that handle_server_command sets correct environment variables."""
        mock_app_args.model = "test-model"

        await handle_server_command(mock_app_args)

        call_env = patch_server_dependencies["popen"].call_args[1]["env"]
        assert call_env["LANGREPL_WORKING_DIR"] == mock_app_args.working_dir
        assert call_env["LANGREPL_AGENT"] == "test-agent"
        assert call_env["LANGREPL_MODEL"] == "test-model"

    @pytest.mark.asyncio
    @patch(
        "src.cli.bootstrap.server._wait_for_server_ready",
        new_callable=AsyncMock,
        return_value=True,
    )
    async def test_handle_server_command_waits_for_server(
        self,
        mock_wait,
        mock_app_args,
        patch_server_dependencies,
    ):
        """Test that handle_server_command waits for server to be ready."""
        await handle_server_command(mock_app_args)

        mock_wait.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(
        "src.cli.bootstrap.server._wait_for_server_ready",
        new_callable=AsyncMock,
        return_value=False,
    )
    async def test_handle_server_command_kills_on_timeout(
        self,
        mock_wait,
        mock_app_args,
        patch_server_dependencies,
    ):
        """Test that handle_server_command terminates process on timeout."""
        result = await handle_server_command(mock_app_args)

        mock_wait.assert_awaited_once()
        patch_server_dependencies["process"].terminate.assert_called_once()
        patch_server_dependencies["process"].wait.assert_called()
        assert result == 1

    @pytest.mark.asyncio
    async def test_handle_server_command_handles_exception(
        self, mock_app_args, patch_server_dependencies
    ):
        """Test that handle_server_command handles exceptions gracefully."""
        patch_server_dependencies["initializer"].load_agent_config.side_effect = (
            Exception("Config error")
        )

        result = await handle_server_command(mock_app_args)

        assert result == 1

    @pytest.mark.asyncio
    async def test_handle_server_command_adds_gitignore(
        self, mock_app_args, patch_server_dependencies
    ):
        """Test that handle_server_command adds .langgraph_api to gitignore."""
        git_dir = Path(mock_app_args.working_dir) / ".git" / "info"
        git_dir.mkdir(parents=True)

        await handle_server_command(mock_app_args)

        exclude_file = git_dir / "exclude"
        assert exclude_file.exists()
        content = exclude_file.read_text()
        assert ".langgraph_api/" in content
