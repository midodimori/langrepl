"""Tests for ApproveHandler."""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from langrepl.cli.handlers.approve import ApproveHandler
from langrepl.configs import ToolApprovalConfig, ToolApprovalRule


class TestApproveHandler:
    """Tests for ApproveHandler class."""

    @pytest.fixture
    def mock_session(self, tmp_path):
        """Create a mock session for testing."""
        session = Mock()
        session.context = Mock()
        session.context.working_dir = str(tmp_path)
        session.context.bash_mode = False
        session.context.approval_mode = Mock()
        session.context.approval_mode.value = "semi-active"
        return session

    def test_format_rule_with_args(self):
        """Test formatting a rule with arguments."""
        session = Mock()
        handler = ApproveHandler(session)
        rule = ToolApprovalRule(name="run_command", args={"command": r"rm\s+-rf.*"})

        result = handler._format_rule(rule)

        assert result == r"run_command: command=rm\s+-rf.*"

    def test_format_rule_with_multiple_args(self):
        """Test formatting a rule with multiple arguments."""
        session = Mock()
        handler = ApproveHandler(session)
        rule = ToolApprovalRule(name="read_file", args={"path": "/etc/.*", "mode": "r"})

        result = handler._format_rule(rule)

        assert "read_file:" in result
        assert "path=/etc/.*" in result
        assert "mode=r" in result

    def test_format_rule_without_args(self):
        """Test formatting a rule without arguments."""
        session = Mock()
        handler = ApproveHandler(session)
        rule = ToolApprovalRule(name="read_file", args=None)

        result = handler._format_rule(rule)

        assert result == "read_file"


class TestToolApprovalConfigWithAlwaysAsk:
    """Tests for ToolApprovalConfig with always_ask field."""

    def test_default_always_ask_rules_from_file(self):
        """Test that default always_ask rules are populated when loading from non-existent file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.approval.json"
            # File doesn't exist - should get defaults
            config = ToolApprovalConfig.from_json_file(config_file)

            assert len(config.always_ask) == 4
            assert all(r.name == "run_command" for r in config.always_ask)

            # Check specific patterns
            patterns = [r.args["command"] for r in config.always_ask if r.args]
            assert r"rm\s+-rf.*" in patterns
            assert r"git\s+push.*" in patterns
            assert r"git\s+reset\s+--hard.*" in patterns
            assert r"sudo\s+.*" in patterns

    def test_empty_always_ask_when_created_directly(self):
        """Test that ToolApprovalConfig() has empty always_ask."""
        config = ToolApprovalConfig()
        assert len(config.always_ask) == 0

    def test_load_config_preserves_existing_rules(self):
        """Test that loading config preserves existing rules and adds defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.approval.json"

            # Create config with custom rules (no always_ask field)
            original = ToolApprovalConfig(
                always_allow=[ToolApprovalRule(name="read_file", args=None)],
                always_deny=[ToolApprovalRule(name="delete_file", args=None)],
                always_ask=[],  # Empty to simulate existing config
            )
            original.save_to_json_file(config_file)

            # Reload - existing rules should be preserved
            loaded = ToolApprovalConfig.from_json_file(config_file)

            assert len(loaded.always_allow) == 1
            assert len(loaded.always_deny) == 1
            assert len(loaded.always_ask) == 0  # Was explicitly set to empty

    def test_save_and_reload_with_always_ask(self):
        """Test saving and reloading config with always_ask rules."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.approval.json"

            config = ToolApprovalConfig(
                always_allow=[],
                always_deny=[],
                always_ask=[
                    ToolApprovalRule(name="custom_tool", args={"arg": "value"})
                ],
            )
            config.save_to_json_file(config_file)

            loaded = ToolApprovalConfig.from_json_file(config_file)

            assert len(loaded.always_ask) == 1
            assert loaded.always_ask[0].name == "custom_tool"
            assert loaded.always_ask[0].args == {"arg": "value"}


class TestSaveApprovalDecisionWithAlwaysAsk:
    """Tests for _save_approval_decision with always_ask handling."""

    def test_save_decision_removes_from_always_ask(self):
        """Test that permanent decisions remove from always_ask."""
        from langrepl.middlewares.approval import ApprovalMiddleware

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.approval.json"

            config = ToolApprovalConfig(
                always_allow=[],
                always_deny=[],
                always_ask=[
                    ToolApprovalRule(
                        name="run_command", args={"command": r"git\s+push.*"}
                    )
                ],
            )
            config.save_to_json_file(config_file)

            # Save a permanent allow decision
            ApprovalMiddleware._save_approval_decision(
                config,
                config_file,
                "run_command",
                {"command": r"git\s+push.*"},
                allow=True,
                from_always_ask=True,
            )

            # Reload and verify
            loaded = ToolApprovalConfig.from_json_file(config_file)
            assert len(loaded.always_ask) == 0
            assert len(loaded.always_allow) == 1

    def test_save_decision_preserves_always_ask_on_onetime(self):
        """Test that one-time decisions preserve always_ask membership."""

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.approval.json"

            config = ToolApprovalConfig(
                always_allow=[],
                always_deny=[],
                always_ask=[
                    ToolApprovalRule(
                        name="run_command", args={"command": r"git\s+push.*"}
                    )
                ],
            )
            config.save_to_json_file(config_file)

            # One-time decisions don't call _save_approval_decision
            # So always_ask should remain unchanged
            loaded = ToolApprovalConfig.from_json_file(config_file)
            assert len(loaded.always_ask) == 1
