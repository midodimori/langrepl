import pytest

from src.core.config import BatchAgentConfig, ToolApprovalRule


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
