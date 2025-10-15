import pytest

from src.core.config import (
    BatchAgentConfig,
    CheckpointerProvider,
    LLMProvider,
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
    def test_explicit_default(self):
        from src.core.config import AgentConfig, CheckpointerConfig, LLMConfig

        config = BatchAgentConfig(
            agents=[
                AgentConfig(
                    name="agent1",
                    default=False,
                    llm=LLMConfig(
                        provider=LLMProvider.OPENAI,
                        model="gpt-4",
                        max_tokens=1000,
                        temperature=0.7,
                    ),
                    checkpointer=CheckpointerConfig(type=CheckpointerProvider.MEMORY),
                ),
                AgentConfig(
                    name="agent2",
                    default=True,
                    llm=LLMConfig(
                        provider=LLMProvider.OPENAI,
                        model="gpt-4",
                        max_tokens=1000,
                        temperature=0.7,
                    ),
                    checkpointer=CheckpointerConfig(type=CheckpointerProvider.MEMORY),
                ),
            ]
        )
        default_agent = config.get_default_agent()
        assert default_agent is not None
        assert default_agent.name == "agent2"

    def test_no_explicit_default_returns_first(self):
        from src.core.config import AgentConfig, CheckpointerConfig, LLMConfig

        config = BatchAgentConfig(
            agents=[
                AgentConfig(
                    name="agent1",
                    default=False,
                    llm=LLMConfig(
                        provider=LLMProvider.OPENAI,
                        model="gpt-4",
                        max_tokens=1000,
                        temperature=0.7,
                    ),
                    checkpointer=CheckpointerConfig(type=CheckpointerProvider.MEMORY),
                ),
                AgentConfig(
                    name="agent2",
                    default=False,
                    llm=LLMConfig(
                        provider=LLMProvider.OPENAI,
                        model="gpt-4",
                        max_tokens=1000,
                        temperature=0.7,
                    ),
                    checkpointer=CheckpointerConfig(type=CheckpointerProvider.MEMORY),
                ),
            ]
        )
        default_agent = config.get_default_agent()
        assert default_agent is not None
        assert default_agent.name == "agent1"

    def test_empty_agents_returns_none(self):
        config = BatchAgentConfig(agents=[])
        assert config.get_default_agent() is None

    def test_get_agent_by_name(self):
        from src.core.config import AgentConfig, CheckpointerConfig, LLMConfig

        config = BatchAgentConfig(
            agents=[
                AgentConfig(
                    name="agent1",
                    llm=LLMConfig(
                        provider=LLMProvider.OPENAI,
                        model="gpt-4",
                        max_tokens=1000,
                        temperature=0.7,
                    ),
                    checkpointer=CheckpointerConfig(type=CheckpointerProvider.MEMORY),
                ),
                AgentConfig(
                    name="agent2",
                    llm=LLMConfig(
                        provider=LLMProvider.OPENAI,
                        model="gpt-4",
                        max_tokens=1000,
                        temperature=0.7,
                    ),
                    checkpointer=CheckpointerConfig(type=CheckpointerProvider.MEMORY),
                ),
            ]
        )
        agent2 = config.get_agent_config("agent2")
        assert agent2 is not None
        assert agent2.name == "agent2"
        assert config.get_agent_config("nonexistent") is None


class TestBatchAgentConfigValidation:
    def test_multiple_defaults_raises_error(self):
        from src.core.config import AgentConfig, CheckpointerConfig, LLMConfig

        with pytest.raises(ValueError, match="Multiple agents marked as default"):
            BatchAgentConfig(
                agents=[
                    AgentConfig(
                        name="agent1",
                        default=True,
                        llm=LLMConfig(
                            provider=LLMProvider.OPENAI,
                            model="gpt-4",
                            max_tokens=1000,
                            temperature=0.7,
                        ),
                        checkpointer=CheckpointerConfig(
                            type=CheckpointerProvider.MEMORY
                        ),
                    ),
                    AgentConfig(
                        name="agent2",
                        default=True,
                        llm=LLMConfig(
                            provider=LLMProvider.OPENAI,
                            model="gpt-4",
                            max_tokens=1000,
                            temperature=0.7,
                        ),
                        checkpointer=CheckpointerConfig(
                            type=CheckpointerProvider.MEMORY
                        ),
                    ),
                ]
            )

    def test_single_default_is_valid(self):
        from src.core.config import AgentConfig, CheckpointerConfig, LLMConfig

        config = BatchAgentConfig(
            agents=[
                AgentConfig(
                    name="agent1",
                    default=True,
                    llm=LLMConfig(
                        provider=LLMProvider.OPENAI,
                        model="gpt-4",
                        max_tokens=1000,
                        temperature=0.7,
                    ),
                    checkpointer=CheckpointerConfig(type=CheckpointerProvider.MEMORY),
                ),
            ]
        )
        default_agent = config.get_default_agent()
        assert default_agent is not None
        assert default_agent.name == "agent1"
