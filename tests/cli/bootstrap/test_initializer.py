"""Tests for initializer module."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.cli.bootstrap.initializer import Initializer
from src.core.config import (
    AgentConfig,
    BatchAgentConfig,
    BatchCheckpointerConfig,
    BatchLLMConfig,
    CheckpointerConfig,
    CheckpointerProvider,
    LLMConfig,
)
from src.core.constants import (
    CONFIG_AGENTS_DIR,
    CONFIG_CHECKPOINTERS_DIR,
    CONFIG_DIR_NAME,
    CONFIG_LLMS_DIR,
    CONFIG_MEMORY_FILE_NAME,
    CONFIG_SUBAGENTS_DIR,
)


class TestInitializer:
    """Tests for Initializer class."""

    @pytest.mark.asyncio
    async def test_ensure_config_dir_creates_directory(self, temp_dir, initializer):
        """Test that _ensure_config_dir creates .langrepl directory."""
        config_dir = temp_dir / CONFIG_DIR_NAME
        assert not config_dir.exists()

        await initializer._ensure_config_dir(temp_dir)

        assert config_dir.exists()
        assert config_dir.is_dir()

    @pytest.mark.asyncio
    async def test_ensure_config_dir_copies_template_files(self, config_dir):
        """Test that _ensure_config_dir copies template files."""
        config_path = config_dir / CONFIG_DIR_NAME
        assert (config_path / CONFIG_AGENTS_DIR.name).exists()
        assert (config_path / CONFIG_LLMS_DIR.name).exists()
        assert (config_path / CONFIG_CHECKPOINTERS_DIR.name).exists()
        assert (config_path / CONFIG_SUBAGENTS_DIR.name).exists()

    @pytest.mark.asyncio
    async def test_ensure_config_dir_adds_gitignore(self, temp_dir, initializer):
        """Test that _ensure_config_dir adds .langrepl to git exclude."""
        git_dir = temp_dir / ".git" / "info"
        git_dir.mkdir(parents=True)
        exclude_file = git_dir / "exclude"

        await initializer._ensure_config_dir(temp_dir)

        assert exclude_file.exists()
        content = exclude_file.read_text()
        assert CONFIG_DIR_NAME in content

    @pytest.mark.asyncio
    async def test_ensure_config_dir_does_not_overwrite_existing(
        self, temp_dir, initializer
    ):
        """Test that _ensure_config_dir doesn't overwrite existing files."""
        config_path = temp_dir / CONFIG_DIR_NAME
        config_path.mkdir()
        test_file = config_path / "test.txt"
        test_file.write_text("existing content")

        await initializer._ensure_config_dir(temp_dir)

        assert test_file.exists()
        assert test_file.read_text() == "existing content"

    @pytest.mark.asyncio
    async def test_load_llms_config_returns_batch_config(self, config_dir, initializer):
        """Test that load_llms_config returns BatchLLMConfig."""
        result = await initializer.load_llms_config(config_dir)

        assert isinstance(result, BatchLLMConfig)
        assert hasattr(result, "llms")

    @pytest.mark.asyncio
    @patch.object(Initializer, "load_llms_config")
    async def test_load_llm_config_returns_specific_llm(
        self,
        mock_load_llms_config,
        config_dir,
        initializer,
        mock_llm_config,
    ):
        """Test that load_llm_config returns specific LLM config."""
        mock_load_llms_config.return_value = MagicMock(
            llms=[mock_llm_config],
            get_llm_config=MagicMock(return_value=mock_llm_config),
        )

        result = await initializer.load_llm_config("test-model", config_dir)

        assert isinstance(result, LLMConfig)
        assert result.alias == "test-model"

    @pytest.mark.asyncio
    @patch.object(Initializer, "load_llms_config")
    async def test_load_llm_config_raises_on_missing_model(
        self,
        mock_load_llms_config,
        config_dir,
        initializer,
    ):
        """Test that load_llm_config raises ValueError for missing model."""
        mock_load_llms_config.return_value = MagicMock(
            llm_names=["model1", "model2"],
            get_llm_config=MagicMock(return_value=None),
        )

        with pytest.raises(ValueError, match="not found"):
            await initializer.load_llm_config("nonexistent", config_dir)

    @pytest.mark.asyncio
    async def test_load_agents_config_returns_batch_config(
        self, config_dir, initializer
    ):
        """Test that load_agents_config returns BatchAgentConfig."""
        result = await initializer.load_agents_config(config_dir)

        assert isinstance(result, BatchAgentConfig)
        assert hasattr(result, "agents")

    @pytest.mark.asyncio
    @patch.object(Initializer, "load_agents_config")
    async def test_load_agent_config_returns_specific_agent(
        self,
        mock_load_agents_config,
        config_dir,
        initializer,
        mock_agent_config,
    ):
        """Test that load_agent_config returns specific agent config."""
        mock_load_agents_config.return_value = MagicMock(
            agents=[mock_agent_config],
            get_agent_config=MagicMock(return_value=mock_agent_config),
        )

        result = await initializer.load_agent_config("test-agent", config_dir)

        assert isinstance(result, AgentConfig)
        assert result.name == "test-agent"

    @pytest.mark.asyncio
    @patch.object(Initializer, "load_agents_config")
    async def test_load_agent_config_raises_on_missing_agent(
        self,
        mock_load_agents_config,
        config_dir,
        initializer,
    ):
        """Test that load_agent_config raises ValueError for missing agent."""
        mock_load_agents_config.return_value = MagicMock(
            agent_names=["agent1", "agent2"],
            get_agent_config=MagicMock(return_value=None),
        )

        with pytest.raises(ValueError, match="not found"):
            await initializer.load_agent_config("nonexistent", config_dir)

    @pytest.mark.asyncio
    async def test_load_user_memory_returns_formatted_content(self, temp_dir):
        """Test that load_user_memory returns properly formatted content."""
        memory_path = temp_dir / CONFIG_MEMORY_FILE_NAME
        memory_path.parent.mkdir(parents=True, exist_ok=True)
        memory_path.write_text("User preferences\nSome context")

        result = await Initializer.load_user_memory(temp_dir)

        assert "<user-memory>" in result
        assert "</user-memory>" in result
        assert "User preferences" in result

    @pytest.mark.asyncio
    async def test_load_user_memory_returns_empty_string_when_missing(self, temp_dir):
        """Test that load_user_memory returns empty string when file doesn't exist."""
        result = await Initializer.load_user_memory(temp_dir)

        assert result == ""

    @pytest.mark.asyncio
    async def test_load_user_memory_returns_empty_string_when_empty(self, temp_dir):
        """Test that load_user_memory returns empty string for empty file."""
        memory_path = temp_dir / CONFIG_MEMORY_FILE_NAME
        memory_path.parent.mkdir(parents=True, exist_ok=True)
        memory_path.write_text("   \n  ")

        result = await Initializer.load_user_memory(temp_dir)

        assert result == ""

    @pytest.mark.asyncio
    @patch.object(BatchAgentConfig, "update_agent_llm", new_callable=AsyncMock)
    async def test_update_agent_llm_modifies_config(
        self,
        mock_update_agent_llm,
        config_dir,
    ):
        """Test that update_agent_llm updates agent config file."""
        await Initializer.update_agent_llm("test-agent", "new-model", config_dir)

        mock_update_agent_llm.assert_awaited_once()
        kwargs = mock_update_agent_llm.call_args.kwargs
        assert kwargs["agent_name"] == "test-agent"
        assert kwargs["new_llm_name"] == "new-model"

    @pytest.mark.asyncio
    @patch.object(BatchAgentConfig, "update_agent_llm", new_callable=AsyncMock)
    async def test_update_subagent_llm_modifies_config(
        self,
        mock_update_agent_llm,
        config_dir,
    ):
        """Test that update_subagent_llm updates subagent config file."""
        await Initializer.update_subagent_llm("test-subagent", "new-model", config_dir)

        mock_update_agent_llm.assert_awaited_once()
        kwargs = mock_update_agent_llm.call_args.kwargs
        assert kwargs["agent_name"] == "test-subagent"
        assert kwargs["new_llm_name"] == "new-model"

    @pytest.mark.asyncio
    @patch.object(BatchAgentConfig, "update_default_agent", new_callable=AsyncMock)
    async def test_update_default_agent_modifies_config(
        self,
        mock_update_default_agent,
        config_dir,
    ):
        """Test that update_default_agent updates default agent."""
        await Initializer.update_default_agent("test-agent", config_dir)

        mock_update_default_agent.assert_awaited_once()
        kwargs = mock_update_default_agent.call_args.kwargs
        assert kwargs["agent_name"] == "test-agent"

    @pytest.mark.asyncio
    @patch.object(Initializer, "load_agent_config")
    async def test_get_checkpointer_returns_checkpointer(
        self,
        mock_load_agent_config,
        config_dir,
        initializer,
        mock_agent_config,
    ):
        """Test that get_checkpointer returns a checkpointer instance."""
        mock_agent_config.checkpointer = CheckpointerConfig(
            type=CheckpointerProvider.MEMORY
        )

        mock_load_agent_config.return_value = mock_agent_config

        async with initializer.get_checkpointer("test-agent", config_dir) as cp:
            assert cp is not None

    @pytest.mark.asyncio
    @patch.object(Initializer, "load_mcp_config")
    @patch.object(Initializer, "load_llm_config")
    @patch.object(Initializer, "load_agent_config")
    async def test_get_graph_creates_compiled_graph(
        self,
        mock_load_agent_config,
        mock_load_llm_config,
        mock_load_mcp_config,
        config_dir,
        initializer,
        mock_agent_config,
        mock_llm_config,
    ):
        """Test that get_graph creates a compiled graph."""
        mock_agent_config.checkpointer = CheckpointerConfig(
            type=CheckpointerProvider.MEMORY
        )

        mock_load_agent_config.return_value = mock_agent_config
        mock_load_llm_config.return_value = mock_llm_config
        mock_load_mcp_config.return_value = MagicMock(servers={})

        async with initializer.get_graph(
            "test-agent", "test-model", config_dir
        ) as graph:
            assert graph is not None
            assert hasattr(graph, "invoke")

    @pytest.mark.asyncio
    @patch.object(Initializer, "get_checkpointer")
    async def test_get_threads_returns_thread_list(
        self,
        mock_get_checkpointer,
        config_dir,
        initializer,
        mock_checkpointer,
    ):
        """Test that get_threads returns list of threads."""
        thread_id = str(uuid.uuid4())

        async def mock_alist(*args, **kwargs):
            yield MagicMock(
                config={"configurable": {"thread_id": thread_id}},
                checkpoint={
                    "channel_values": {"messages": [MagicMock(text="Test message")]},
                    "ts": "2024-01-01T00:00:00.000Z",
                },
            )

        mock_checkpointer.alist = mock_alist

        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_checkpointer
        mock_get_checkpointer.return_value = mock_context_manager

        threads = await initializer.get_threads("test-agent", config_dir)

        assert isinstance(threads, list)

    @pytest.mark.asyncio
    @patch.object(Initializer, "get_checkpointer")
    async def test_get_threads_handles_empty_checkpointer(
        self,
        mock_get_checkpointer,
        config_dir,
        initializer,
        mock_checkpointer,
    ):
        """Test that get_threads handles empty checkpointer gracefully."""

        async def mock_alist(*args, **kwargs):
            return
            yield

        mock_checkpointer.alist = mock_alist
        mock_checkpointer.aget_tuple = AsyncMock(return_value=None)

        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_checkpointer
        mock_get_checkpointer.return_value = mock_context_manager

        threads = await initializer.get_threads("test-agent", config_dir)

        assert threads == []

    @pytest.mark.asyncio
    @patch.object(Initializer, "get_checkpointer")
    async def test_get_threads_sorts_by_timestamp(
        self,
        mock_get_checkpointer,
        config_dir,
        initializer,
        mock_checkpointer,
    ):
        """Test that get_threads sorts threads by timestamp."""
        thread_id_1 = str(uuid.uuid4())
        thread_id_2 = str(uuid.uuid4())

        mock_checkpointer.get_threads = AsyncMock(
            return_value={thread_id_1, thread_id_2}
        )

        mock_checkpointer.aget_tuple = AsyncMock(
            side_effect=[
                MagicMock(
                    checkpoint={
                        "channel_values": {"messages": [MagicMock(text="Old message")]},
                        "ts": "2024-01-01T00:00:00.000Z",
                    }
                ),
                MagicMock(
                    checkpoint={
                        "channel_values": {"messages": [MagicMock(text="New message")]},
                        "ts": "2024-01-02T00:00:00.000Z",
                    }
                ),
            ]
        )

        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_checkpointer
        mock_get_checkpointer.return_value = mock_context_manager

        threads = await initializer.get_threads("test-agent", config_dir)

        assert len(threads) == 2
        assert threads[0]["timestamp"] > threads[1]["timestamp"]

    @pytest.mark.asyncio
    async def test_load_checkpointers_config_returns_batch_config(
        self, config_dir, initializer
    ):
        """Test that load_checkpointers_config returns BatchCheckpointerConfig."""
        result = await initializer.load_checkpointers_config(config_dir)

        assert isinstance(result, BatchCheckpointerConfig)
        assert hasattr(result, "checkpointers")

    @pytest.mark.asyncio
    async def test_load_subagents_config_returns_batch_config(
        self, config_dir, initializer
    ):
        """Test that load_subagents_config returns BatchAgentConfig."""
        result = await initializer.load_subagents_config(config_dir)

        assert isinstance(result, BatchAgentConfig)
        assert hasattr(result, "agents")
