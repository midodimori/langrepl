import pytest
import yaml

from src.core.config import (
    BatchAgentConfig,
    BatchCheckpointerConfig,
    BatchLLMConfig,
    ToolApprovalRule,
)


class TestToolApprovalRuleMatchesCall:
    def test_exact_name_match_no_args(self):
        rule = ToolApprovalRule(name="read_file", args=None)
        assert rule.matches_call("read_file", {}) is True
        assert rule.matches_call("read_file", {"path": "/tmp/file"}) is True

    def test_name_mismatch(self):
        rule = ToolApprovalRule(name="read_file", args=None)
        assert rule.matches_call("write_file", {}) is False

    def test_exact_args_match(self):
        rule = ToolApprovalRule(name="read_file", args={"path": "/tmp/test"})
        assert rule.matches_call("read_file", {"path": "/tmp/test"}) is True

    def test_args_mismatch(self):
        rule = ToolApprovalRule(name="read_file", args={"path": "/tmp/test"})
        assert rule.matches_call("read_file", {"path": "/tmp/other"}) is False

    def test_regex_pattern_match(self):
        rule = ToolApprovalRule(name="read_file", args={"path": r"/tmp/.*"})
        assert rule.matches_call("read_file", {"path": "/tmp/test"}) is True
        assert rule.matches_call("read_file", {"path": "/tmp/file.txt"}) is True

    def test_regex_pattern_no_match(self):
        rule = ToolApprovalRule(name="read_file", args={"path": r"/tmp/.*"})
        assert rule.matches_call("read_file", {"path": "/home/test"}) is False

    def test_missing_required_arg(self):
        rule = ToolApprovalRule(name="read_file", args={"path": "/tmp/test"})
        assert rule.matches_call("read_file", {}) is False

    def test_multiple_args_all_match(self):
        rule = ToolApprovalRule(
            name="copy_file", args={"src": "/tmp/.*", "dst": "/backup/.*"}
        )
        assert (
            rule.matches_call("copy_file", {"src": "/tmp/file", "dst": "/backup/file"})
            is True
        )

    def test_multiple_args_partial_match(self):
        rule = ToolApprovalRule(
            name="copy_file", args={"src": "/tmp/.*", "dst": "/backup/.*"}
        )
        assert (
            rule.matches_call("copy_file", {"src": "/tmp/file", "dst": "/home/file"})
            is False
        )


class TestBatchAgentConfigGetDefaultAgent:
    def test_explicit_default(self, mock_agent_config):
        agent1 = mock_agent_config.model_copy(
            update={"name": "agent1", "default": False}
        )
        agent2 = mock_agent_config.model_copy(
            update={"name": "agent2", "default": True}
        )

        config = BatchAgentConfig(agents=[agent1, agent2])
        default_agent = config.get_default_agent()
        assert default_agent is not None
        assert default_agent.name == "agent2"

    def test_no_explicit_default_returns_first(self, mock_agent_config):
        agent1 = mock_agent_config.model_copy(
            update={"name": "agent1", "default": False}
        )
        agent2 = mock_agent_config.model_copy(
            update={"name": "agent2", "default": False}
        )

        config = BatchAgentConfig(agents=[agent1, agent2])
        default_agent = config.get_default_agent()
        assert default_agent is not None
        assert default_agent.name == "agent1"

    def test_empty_agents_returns_none(self):
        config = BatchAgentConfig(agents=[])
        assert config.get_default_agent() is None

    def test_get_agent_by_name(self, mock_agent_config):
        agent1 = mock_agent_config.model_copy(update={"name": "agent1"})
        agent2 = mock_agent_config.model_copy(update={"name": "agent2"})

        config = BatchAgentConfig(agents=[agent1, agent2])
        agent2 = config.get_agent_config("agent2")
        assert agent2 is not None
        assert agent2.name == "agent2"
        assert config.get_agent_config("nonexistent") is None


class TestBatchAgentConfigValidation:
    def test_multiple_defaults_raises_error(self, mock_agent_config):
        agent1 = mock_agent_config.model_copy(
            update={"name": "agent1", "default": True}
        )
        agent2 = mock_agent_config.model_copy(
            update={"name": "agent2", "default": True}
        )

        with pytest.raises(ValueError, match="Multiple agents marked as default"):
            BatchAgentConfig(agents=[agent1, agent2])

    def test_single_default_is_valid(self, mock_agent_config):
        agent1 = mock_agent_config.model_copy(
            update={"name": "agent1", "default": True}
        )

        config = BatchAgentConfig(agents=[agent1])
        default_agent = config.get_default_agent()
        assert default_agent is not None
        assert default_agent.name == "agent1"


class TestDuplicateValidation:
    """Test duplicate detection in configs."""

    @pytest.mark.asyncio
    async def test_duplicate_agents(self, temp_dir, mock_llm_config):
        """Test that duplicate agent names raise an error."""
        file_path = temp_dir / "config.agents.yml"
        file_path.write_text(
            yaml.dump(
                {
                    "agents": [
                        {"name": "my-agent", "default": True, "llm": "test-model"},
                        {"name": "my-agent", "llm": "test-model"},  # Duplicate
                    ]
                }
            )
        )

        batch_llm = BatchLLMConfig(llms=[mock_llm_config])

        with pytest.raises(ValueError, match=r"Duplicate agent 'name': 'my-agent'"):
            await BatchAgentConfig.from_yaml(
                file_path=file_path, batch_llm_config=batch_llm
            )

    @pytest.mark.asyncio
    async def test_duplicate_llms(self, temp_dir):
        """Test that duplicate LLM aliases raise an error."""
        file_path = temp_dir / "config.llms.yml"
        file_path.write_text(
            yaml.dump(
                {
                    "llms": [
                        {
                            "alias": "model",
                            "provider": "anthropic",
                            "model": "claude-3-5-sonnet-20241022",
                            "max_tokens": 4096,
                            "temperature": 0.7,
                        },
                        {
                            "alias": "model",  # Duplicate
                            "provider": "openai",
                            "model": "gpt-4",
                            "max_tokens": 8192,
                            "temperature": 0.5,
                        },
                    ]
                }
            )
        )

        with pytest.raises(ValueError, match=r"Duplicate llm 'alias': 'model'"):
            await BatchLLMConfig.from_yaml(file_path=file_path)

    @pytest.mark.asyncio
    async def test_duplicate_checkpointers(self, temp_dir):
        """Test that duplicate checkpointer types raise an error."""
        file_path = temp_dir / "config.checkpointers.yml"
        file_path.write_text(
            yaml.dump(
                {
                    "checkpointers": [
                        {"type": "sqlite", "max_connections": 10},
                        {"type": "sqlite", "max_connections": 20},  # Duplicate
                    ]
                }
            )
        )

        with pytest.raises(
            ValueError, match=r"Duplicate checkpointer 'type': 'sqlite'"
        ):
            await BatchCheckpointerConfig.from_yaml(file_path=file_path)

    @pytest.mark.asyncio
    async def test_missing_key_raises_error(self, temp_dir):
        """Test that missing required key raises an error."""
        file_path = temp_dir / "config.llms.yml"
        file_path.write_text(
            yaml.dump(
                {
                    "llms": [
                        {
                            "provider": "anthropic",  # Missing 'alias' key
                            "model": "claude-3-5-sonnet-20241022",
                            "max_tokens": 4096,
                            "temperature": 0.7,
                        }
                    ]
                }
            )
        )

        with pytest.raises(ValueError, match=r"missing required key 'alias'"):
            await BatchLLMConfig.from_yaml(file_path=file_path)

    @pytest.mark.asyncio
    async def test_unique_items_load_successfully(
        self, temp_dir, mock_llm_config, mock_checkpointer_config
    ):
        """Test that configs with unique items from file and directory load successfully."""
        file_path = temp_dir / "config.agents.yml"
        file_path.write_text(
            yaml.dump(
                {
                    "agents": [
                        {
                            "name": "agent1",
                            "default": True,
                            "llm": "test-model",
                            "checkpointer": "memory",
                        }
                    ]
                }
            )
        )

        dir_path = temp_dir / "agents"
        dir_path.mkdir()
        (dir_path / "agent2.yml").write_text(
            yaml.dump({"name": "agent2", "llm": "test-model"})
        )

        batch_llm = BatchLLMConfig(llms=[mock_llm_config])
        batch_checkpointer = BatchCheckpointerConfig(
            checkpointers=[mock_checkpointer_config]
        )

        config = await BatchAgentConfig.from_yaml(
            file_path=file_path,
            dir_path=dir_path,
            batch_llm_config=batch_llm,
            batch_checkpointer_config=batch_checkpointer,
        )

        assert len(config.agents) == 2
        assert set(config.agent_names) == {"agent1", "agent2"}


class TestFilenameValidation:
    """Test filename validation for directory-based configs."""

    @pytest.mark.asyncio
    async def test_agent_filename_mismatch_raises_error(
        self, temp_dir, mock_llm_config
    ):
        """Test that agent filename must match agent name."""
        dir_path = temp_dir / "agents"
        dir_path.mkdir()
        (dir_path / "wrong-name.yml").write_text(
            yaml.dump({"name": "correct-name", "llm": "test-model", "default": True})
        )

        batch_llm = BatchLLMConfig(llms=[mock_llm_config])

        with pytest.raises(
            ValueError,
            match=r"Agent file 'wrong-name.yml' has name='correct-name' but filename is 'wrong-name'",
        ):
            await BatchAgentConfig.from_yaml(
                dir_path=dir_path, batch_llm_config=batch_llm
            )

    @pytest.mark.asyncio
    async def test_checkpointer_filename_mismatch_raises_error(self, temp_dir):
        """Test that checkpointer filename must match checkpointer type."""
        dir_path = temp_dir / "checkpointers"
        dir_path.mkdir()
        (dir_path / "wrong-type.yml").write_text(
            yaml.dump({"type": "sqlite", "max_connections": 10})
        )

        with pytest.raises(
            ValueError,
            match=r"Checkpointer file 'wrong-type.yml' has type='sqlite' but filename is 'wrong-type'",
        ):
            await BatchCheckpointerConfig.from_yaml(dir_path=dir_path)

    @pytest.mark.asyncio
    async def test_matching_filenames_load_successfully(
        self, temp_dir, mock_llm_config
    ):
        """Test that correctly named files load successfully."""
        # Agents
        agents_dir = temp_dir / "agents"
        agents_dir.mkdir()
        (agents_dir / "my-agent.yml").write_text(
            yaml.dump({"name": "my-agent", "llm": "test-model", "default": True})
        )

        # Checkpointers
        checkpointers_dir = temp_dir / "checkpointers"
        checkpointers_dir.mkdir()
        (checkpointers_dir / "memory.yml").write_text(
            yaml.dump({"type": "memory", "max_connections": 10})
        )

        # All should load successfully
        agents_config = await BatchAgentConfig.from_yaml(
            dir_path=agents_dir, batch_llm_config=BatchLLMConfig(llms=[mock_llm_config])
        )
        checkpointers_config = await BatchCheckpointerConfig.from_yaml(
            dir_path=checkpointers_dir
        )

        assert len(agents_config.agents) == 1
        assert len(checkpointers_config.checkpointers) == 1


class TestVersionMigration:
    @pytest.mark.asyncio
    async def test_llm_config_migration_from_no_version(self, temp_dir):
        file_path = temp_dir / "config.llms.yml"
        file_path.write_text(
            yaml.dump(
                {
                    "llms": [
                        {
                            "alias": "test-model",
                            "provider": "anthropic",
                            "model": "claude-3-5-sonnet-20241022",
                            "max_tokens": 4096,
                            "temperature": 0.7,
                        }
                    ]
                }
            )
        )

        config = await BatchLLMConfig.from_yaml(file_path=file_path)
        assert len(config.llms) == 1
        assert config.llms[0].alias == "test-model"

        content = yaml.safe_load(file_path.read_text())
        assert content["llms"][0]["version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_agent_config_migration_from_old_version(
        self, temp_dir, mock_llm_config
    ):
        file_path = temp_dir / "config.agents.yml"
        file_path.write_text(
            yaml.dump(
                {
                    "agents": [
                        {
                            "version": "0.5.0",
                            "name": "test-agent",
                            "default": True,
                            "llm": "test-model",
                        }
                    ]
                }
            )
        )

        config = await BatchAgentConfig.from_yaml(
            file_path=file_path, batch_llm_config=BatchLLMConfig(llms=[mock_llm_config])
        )
        assert len(config.agents) == 1
        assert config.agents[0].name == "test-agent"

        content = yaml.safe_load(file_path.read_text())
        assert content["agents"][0]["version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_checkpointer_config_no_migration_when_current(self, temp_dir):
        file_path = temp_dir / "config.checkpointers.yml"
        file_path.write_text(
            yaml.dump({"checkpointers": [{"version": "1.0.0", "type": "sqlite"}]})
        )
        original_mtime = file_path.stat().st_mtime

        config = await BatchCheckpointerConfig.from_yaml(file_path=file_path)
        assert len(config.checkpointers) == 1
        assert abs(file_path.stat().st_mtime - original_mtime) < 1

    @pytest.mark.asyncio
    async def test_multi_file_config_migration(self, temp_dir, mock_llm_config):
        dir_path = temp_dir / "agents"
        dir_path.mkdir()
        (dir_path / "agent1.yml").write_text(
            yaml.dump({"name": "agent1", "default": True, "llm": "test-model"})
        )
        (dir_path / "agent2.yml").write_text(
            yaml.dump({"name": "agent2", "llm": "test-model"})
        )

        config = await BatchAgentConfig.from_yaml(
            dir_path=dir_path, batch_llm_config=BatchLLMConfig(llms=[mock_llm_config])
        )
        assert len(config.agents) == 2

        for f in ["agent1.yml", "agent2.yml"]:
            assert yaml.safe_load((dir_path / f).read_text())["version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_mixed_version_migration(self, temp_dir):
        file_path = temp_dir / "config.llms.yml"
        file_path.write_text(
            yaml.dump(
                {
                    "llms": [
                        {
                            "version": "1.0.0",
                            "alias": "model1",
                            "provider": "anthropic",
                            "model": "claude-3-5-sonnet-20241022",
                            "max_tokens": 4096,
                            "temperature": 0.7,
                        },
                        {
                            "alias": "model2",
                            "provider": "openai",
                            "model": "gpt-4",
                            "max_tokens": 8192,
                            "temperature": 0.5,
                        },
                    ]
                }
            )
        )

        config = await BatchLLMConfig.from_yaml(file_path=file_path)
        assert len(config.llms) == 2

        content = yaml.safe_load(file_path.read_text())
        assert all(item["version"] == "1.0.0" for item in content["llms"])

    @pytest.mark.asyncio
    async def test_multi_item_file_preserves_all_items(self, temp_dir):
        dir_path = temp_dir / "llms"
        dir_path.mkdir()
        (dir_path / "anthropic.yml").write_text(
            yaml.dump(
                [
                    {
                        "alias": "model1",
                        "provider": "anthropic",
                        "model": "claude-3-5-sonnet-20241022",
                        "max_tokens": 4096,
                        "temperature": 0.7,
                    },
                    {
                        "version": "0.5.0",
                        "alias": "model2",
                        "provider": "anthropic",
                        "model": "claude-3-5-haiku-20241022",
                        "max_tokens": 8192,
                        "temperature": 0.5,
                    },
                    {
                        "version": "1.0.0",
                        "alias": "model3",
                        "provider": "anthropic",
                        "model": "claude-3-opus-20240229",
                        "max_tokens": 2048,
                        "temperature": 0.3,
                    },
                ]
            )
        )

        config = await BatchLLMConfig.from_yaml(dir_path=dir_path)
        assert len(config.llms) == 3
        assert {llm.alias for llm in config.llms} == {"model1", "model2", "model3"}

        content = yaml.safe_load((dir_path / "anthropic.yml").read_text())
        assert isinstance(content, list) and len(content) == 3
        assert all(item["version"] == "1.0.0" for item in content)
        assert {item["alias"] for item in content} == {"model1", "model2", "model3"}
