"""Tests for config module - migration and registry logic."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.configs.base import _validate_no_duplicates


class TestValidateNoDuplicates:
    """Tests for duplicate key validation."""

    def test_no_duplicates_passes(self):
        """Passes when all keys are unique."""
        items = [{"name": "a"}, {"name": "b"}, {"name": "c"}]
        # Should not raise
        _validate_no_duplicates(items, "name", "Agent")

    def test_duplicate_raises_error(self):
        """Raises ValueError when duplicate keys found."""
        items = [{"name": "a"}, {"name": "b"}, {"name": "a"}]
        with pytest.raises(ValueError, match="Duplicate agent 'name': 'a'"):
            _validate_no_duplicates(items, "name", "Agent")

    def test_missing_key_raises_error(self):
        """Raises ValueError when required key is missing."""
        items = [{"name": "a"}, {"other": "b"}]
        with pytest.raises(ValueError, match="missing required key 'name'"):
            _validate_no_duplicates(items, "name", "Agent")


class TestAgentConfigMigration:
    """Tests for AgentConfig version migrations."""

    def test_migrate_1x_to_2_tools_list_to_config(self):
        """Migrates tools: list[str] to tools: ToolsConfig."""
        from src.configs.agent import BaseAgentConfig

        data = {
            "name": "test",
            "llm": "test-llm",
            "tools": ["impl:*:*", "internal:*:*"],
            "tool_output_max_tokens": 5000,
        }

        result = BaseAgentConfig.migrate(data, "1.0.0")

        assert result["tools"]["patterns"] == ["impl:*:*", "internal:*:*"]
        assert result["tools"]["use_catalog"] is False
        assert result["tools"]["output_max_tokens"] == 5000
        assert "tool_output_max_tokens" not in result

    def test_migrate_1x_preserves_existing_tools_dict(self):
        """Preserves tools dict if already in new format."""
        from src.configs.agent import BaseAgentConfig

        data = {
            "name": "test",
            "llm": "test-llm",
            "tools": {"patterns": ["impl:*:*"], "use_catalog": True},
            "tool_output_max_tokens": 3000,
        }

        result = BaseAgentConfig.migrate(data, "1.0.0")

        assert result["tools"]["patterns"] == ["impl:*:*"]
        assert result["tools"]["use_catalog"] is True
        assert result["tools"]["output_max_tokens"] == 3000

    def test_migrate_2_0_to_2_1_adds_skills(self):
        """Adds skills config in 2.0.0 -> 2.1.0 migration."""
        from src.configs.agent import BaseAgentConfig

        data = {
            "name": "test",
            "llm": "test-llm",
            "version": "2.0.0",
        }

        result = BaseAgentConfig.migrate(data, "2.0.0")

        assert "skills" in result
        assert result["skills"]["patterns"] == []
        assert result["skills"]["use_catalog"] is False

    def test_migrate_2_1_to_2_2_renames_compression_llm(self):
        """Renames compression_llm to llm in 2.1.0 -> 2.2.0 migration."""
        from src.configs.agent import BaseAgentConfig

        data = {
            "name": "test",
            "llm": "test-llm",
            "compression": {
                "compression_llm": "gpt-4o-mini",
                "min_messages": 10,
            },
        }

        with patch.object(BaseAgentConfig, "_copy_missing_prompts"):
            result = BaseAgentConfig.migrate(data, "2.1.0")

        assert result["compression"]["llm"] == "gpt-4o-mini"
        assert "compression_llm" not in result["compression"]
        assert result["compression"]["messages_to_keep"] == 0

    def test_no_migration_needed_for_latest(self):
        """No changes when already at latest version."""
        from src.configs.agent import BaseAgentConfig

        data = {
            "name": "test",
            "llm": "test-llm",
            "tools": {"patterns": []},
            "skills": {"patterns": []},
        }

        latest = BaseAgentConfig.get_latest_version()
        result = BaseAgentConfig.migrate(data.copy(), latest)

        assert result == data


class TestConfigRegistry:
    """Tests for ConfigRegistry caching and lookup."""

    @pytest.fixture
    def mock_registry(self, temp_dir):
        """Create registry with mocked config loading."""
        from src.configs.registry import ConfigRegistry

        # Create minimal config dir
        config_dir = temp_dir / ".langrepl"
        config_dir.mkdir()

        with patch.object(ConfigRegistry, "_ensure_config_dir"):
            registry = ConfigRegistry(temp_dir)
            return registry

    @pytest.mark.asyncio
    async def test_caching_returns_same_instance(self, mock_registry):
        """Cache returns same instance on subsequent calls."""
        mock_batch = MagicMock()
        mock_batch.agents = []

        with patch(
            "src.configs.agent.BatchAgentConfig.from_yaml",
            new_callable=AsyncMock,
            return_value=mock_batch,
        ):
            result1 = await mock_registry.agents()
            result2 = await mock_registry.agents()

        assert result1 is result2

    @pytest.mark.asyncio
    async def test_invalidate_clears_cache(self, mock_registry):
        """Invalidate clears cache, forcing reload."""
        mock_batch1 = MagicMock()
        mock_batch2 = MagicMock()

        with patch(
            "src.configs.agent.BatchAgentConfig.from_yaml",
            new_callable=AsyncMock,
            side_effect=[mock_batch1, mock_batch2],
        ):
            result1 = await mock_registry.agents()
            mock_registry.invalidate("agents")
            result2 = await mock_registry.agents()

        assert result1 is mock_batch1
        assert result2 is mock_batch2
        assert result1 is not result2

    @pytest.mark.asyncio
    async def test_agent_lookup_raises_for_missing(self, mock_registry):
        """Raises ValueError when agent not found."""
        mock_batch = MagicMock()
        mock_batch.get_agent_config.return_value = None
        mock_batch.agent_names = ["default", "other"]

        with patch(
            "src.configs.agent.BatchAgentConfig.from_yaml",
            new_callable=AsyncMock,
            return_value=mock_batch,
        ):
            with pytest.raises(ValueError, match="Agent 'nonexistent' not found"):
                await mock_registry.agent("nonexistent")

    @pytest.mark.asyncio
    async def test_llm_lookup_raises_for_missing(self, mock_registry):
        """Raises ValueError when LLM not found."""
        mock_batch = MagicMock()
        mock_batch.get_llm_config.return_value = None
        mock_batch.llm_names = ["gpt-4", "claude"]

        with patch(
            "src.configs.llm.BatchLLMConfig.from_yaml",
            new_callable=AsyncMock,
            return_value=mock_batch,
        ):
            with pytest.raises(ValueError, match="LLM 'nonexistent' not found"):
                await mock_registry.llm("nonexistent")

    def test_invalidate_specific_key(self, mock_registry):
        """Invalidate with key only clears that key."""
        mock_registry._cache["agents"] = "cached_agents"
        mock_registry._cache["llms"] = "cached_llms"

        mock_registry.invalidate("agents")

        assert "agents" not in mock_registry._cache
        assert mock_registry._cache["llms"] == "cached_llms"

    def test_invalidate_all_clears_everything(self, mock_registry):
        """Invalidate without key clears entire cache."""
        mock_registry._cache["agents"] = "cached_agents"
        mock_registry._cache["llms"] = "cached_llms"

        mock_registry.invalidate()

        assert mock_registry._cache == {}
