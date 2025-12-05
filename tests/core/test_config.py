import pytest
import yaml

from src.core.config import (
    BatchAgentConfig,
    BatchCheckpointerConfig,
    BatchLLMConfig,
    ToolApprovalRule,
)


class TestToolApprovalRuleMatchesCall:
    @pytest.mark.parametrize(
        ("rule_name", "rule_args", "call_name", "call_args", "expected"),
        [
            ("read_file", None, "read_file", {}, True),
            ("read_file", None, "read_file", {"path": "/tmp/file"}, True),
            ("read_file", None, "write_file", {}, False),
            (
                "read_file",
                {"path": "/tmp/test"},
                "read_file",
                {"path": "/tmp/test"},
                True,
            ),
            (
                "read_file",
                {"path": "/tmp/test"},
                "read_file",
                {"path": "/tmp/other"},
                False,
            ),
            ("read_file", {"path": "/tmp/test"}, "read_file", {}, False),
            (
                "read_file",
                {"path": r"/tmp/.*"},
                "read_file",
                {"path": "/tmp/test"},
                True,
            ),
            (
                "read_file",
                {"path": r"/tmp/.*"},
                "read_file",
                {"path": "/home/test"},
                False,
            ),
            (
                "copy_file",
                {"src": "/tmp/.*", "dst": "/backup/.*"},
                "copy_file",
                {"src": "/tmp/file", "dst": "/backup/file"},
                True,
            ),
            (
                "copy_file",
                {"src": "/tmp/.*", "dst": "/backup/.*"},
                "copy_file",
                {"src": "/tmp/file", "dst": "/home/file"},
                False,
            ),
        ],
    )
    def test_matches_call(self, rule_name, rule_args, call_name, call_args, expected):
        rule = ToolApprovalRule(name=rule_name, args=rule_args)
        assert rule.matches_call(call_name, call_args) is expected


class TestBatchAgentConfigGetDefaultAgent:
    def test_default_agent_selection(self, mock_agent_config):
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
        agent2_config = config.get_agent_config("agent2")
        assert agent2_config is not None
        assert agent2_config.name == "agent2"
        assert config.get_agent_config("nonexistent") is None

    def test_no_default_returns_first(self, mock_agent_config):
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
        assert BatchAgentConfig(agents=[]).get_default_agent() is None

    def test_multiple_defaults_raises_error(self, mock_agent_config):
        agent1 = mock_agent_config.model_copy(
            update={"name": "agent1", "default": True}
        )
        agent2 = mock_agent_config.model_copy(
            update={"name": "agent2", "default": True}
        )

        with pytest.raises(ValueError, match="Multiple agents marked as default"):
            BatchAgentConfig(agents=[agent1, agent2])


class TestDuplicateValidation:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("config_class", "file_name", "key", "data"),
        [
            (
                BatchAgentConfig,
                "config.agents.yml",
                "agents",
                [
                    {"name": "my-agent", "default": True, "llm": "test-model"},
                    {"name": "my-agent", "llm": "test-model"},
                ],
            ),
            (
                BatchLLMConfig,
                "config.llms.yml",
                "llms",
                [
                    {
                        "alias": "model",
                        "provider": "anthropic",
                        "model": "claude-3-5-sonnet-20241022",
                        "max_tokens": 4096,
                    },
                    {
                        "alias": "model",
                        "provider": "openai",
                        "model": "gpt-4",
                        "max_tokens": 8192,
                    },
                ],
            ),
            (
                BatchCheckpointerConfig,
                "config.checkpointers.yml",
                "checkpointers",
                [
                    {"type": "sqlite", "max_connections": 10},
                    {"type": "sqlite", "max_connections": 20},
                ],
            ),
        ],
    )
    async def test_duplicate_detection(
        self, temp_dir, mock_llm_config, config_class, file_name, key, data
    ):
        file_path = temp_dir / file_name
        file_path.write_text(yaml.dump({key: data}))

        kwargs = (
            {"batch_llm_config": BatchLLMConfig(llms=[mock_llm_config])}
            if config_class == BatchAgentConfig
            else {}
        )

        with pytest.raises(ValueError, match="Duplicate"):
            await config_class.from_yaml(file_path=file_path, **kwargs)


class TestFilenameValidation:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "config_class",
            "dir_name",
            "file_name",
            "config_key",
            "wrong_value",
            "correct_value",
        ),
        [
            (
                BatchAgentConfig,
                "agents",
                "wrong-name.yml",
                "name",
                "correct-name",
                "wrong-name",
            ),
            (
                BatchCheckpointerConfig,
                "checkpointers",
                "wrong-type.yml",
                "type",
                "sqlite",
                "wrong-type",
            ),
        ],
    )
    async def test_filename_mismatch_raises_error(
        self,
        temp_dir,
        mock_llm_config,
        config_class,
        dir_name,
        file_name,
        config_key,
        wrong_value,
        correct_value,
    ):
        dir_path = temp_dir / dir_name
        dir_path.mkdir()

        config_data = {config_key: wrong_value}
        if config_class == BatchAgentConfig:
            config_data.update({"llm": "test-model", "default": True})

        (dir_path / file_name).write_text(yaml.dump(config_data))

        kwargs = (
            {"batch_llm_config": BatchLLMConfig(llms=[mock_llm_config])}
            if config_class == BatchAgentConfig
            else {}
        )

        with pytest.raises(
            ValueError,
            match=f"{config_key}='{wrong_value}'.*filename is '{correct_value}'",
        ):
            await config_class.from_yaml(dir_path=dir_path, **kwargs)


class TestVersionMigration:
    @pytest.mark.asyncio
    async def test_version_added_when_missing(self, temp_dir):
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

        await BatchLLMConfig.from_yaml(file_path=file_path)

        content = yaml.safe_load(file_path.read_text())
        assert content["llms"][0]["version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_agent_config_migrates_to_latest(self, temp_dir, mock_llm_config):
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

        await BatchAgentConfig.from_yaml(
            file_path=file_path, batch_llm_config=BatchLLMConfig(llms=[mock_llm_config])
        )

        content = yaml.safe_load(file_path.read_text())
        assert content["agents"][0]["version"] == "2.2.0"

    @pytest.mark.asyncio
    async def test_agent_compression_migration(self, temp_dir, mock_llm_config):
        file_path = temp_dir / "config.agents.yml"
        file_path.write_text(
            yaml.dump(
                {
                    "agents": [
                        {
                            "version": "2.1.0",
                            "name": "test-agent",
                            "default": True,
                            "llm": "test-model",
                            "compression": {
                                "auto_compress_enabled": True,
                                "compression_llm": "test-model",
                            },
                        }
                    ]
                }
            )
        )

        await BatchAgentConfig.from_yaml(
            file_path=file_path, batch_llm_config=BatchLLMConfig(llms=[mock_llm_config])
        )

        content = yaml.safe_load(file_path.read_text())
        compression = content["agents"][0]["compression"]
        assert content["agents"][0]["version"] == "2.2.0"
        assert "compression_llm" not in compression
        assert compression["llm"] == "test-model"
        assert compression["messages_to_keep"] == 0

    @pytest.mark.asyncio
    async def test_tool_output_max_tokens_migration(self, temp_dir, mock_llm_config):
        """Test tool_output_max_tokens moves to tools.output_max_tokens in v2.0.0"""
        dir_path = temp_dir / "agents"
        dir_path.mkdir()

        (dir_path / "agent1.yml").write_text(
            yaml.dump(
                {
                    "version": "1.0.0",
                    "name": "agent1",
                    "default": True,
                    "llm": "test-model",
                    "tool_output_max_tokens": 10,
                    "tools": ["impl:file_system:read_file"],
                }
            )
        )

        (dir_path / "agent2.yml").write_text(
            yaml.dump(
                {
                    "version": "1.0.0",
                    "name": "agent2",
                    "llm": "test-model",
                    "tool_output_max_tokens": 20,
                    "tools": {"patterns": ["impl:*:*"], "use_catalog": True},
                }
            )
        )

        (dir_path / "agent3.yml").write_text(
            yaml.dump(
                {
                    "version": "1.0.0",
                    "name": "agent3",
                    "llm": "test-model",
                    "tool_output_max_tokens": 30,
                }
            )
        )

        await BatchAgentConfig.from_yaml(
            dir_path=dir_path, batch_llm_config=BatchLLMConfig(llms=[mock_llm_config])
        )

        agent1 = yaml.safe_load((dir_path / "agent1.yml").read_text())
        assert "tool_output_max_tokens" not in agent1
        assert agent1["tools"]["output_max_tokens"] == 10

        agent2 = yaml.safe_load((dir_path / "agent2.yml").read_text())
        assert "tool_output_max_tokens" not in agent2
        assert agent2["tools"]["output_max_tokens"] == 20

        agent3 = yaml.safe_load((dir_path / "agent3.yml").read_text())
        assert "tool_output_max_tokens" not in agent3
        assert agent3["tools"]["output_max_tokens"] == 30
