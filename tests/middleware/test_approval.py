"""Tests for ApprovalMiddleware."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage

from src.agents.context import AgentContext
from src.core.config import ApprovalMode, ToolApprovalConfig, ToolApprovalRule
from src.middleware.approval import (
    DENY,
    ApprovalMiddleware,
    create_field_extractor,
    create_field_transformer,
)


class TestApprovalMiddleware:
    """Tests for ApprovalMiddleware class."""

    def test_check_approval_rules_with_always_deny(self):
        """Test that always_deny rules are checked first."""
        config = ToolApprovalConfig(
            always_deny=[ToolApprovalRule(name="test_tool", args={"query": "bad"})],
            always_allow=[],
        )

        result = ApprovalMiddleware._check_approval_rules(
            config, "test_tool", {"query": "bad"}
        )

        assert result is False

    def test_check_approval_rules_with_always_allow(self):
        """Test that always_allow rules work."""
        config = ToolApprovalConfig(
            always_deny=[],
            always_allow=[ToolApprovalRule(name="test_tool", args={"query": "good"})],
        )

        result = ApprovalMiddleware._check_approval_rules(
            config, "test_tool", {"query": "good"}
        )

        assert result is True

    def test_check_approval_rules_with_no_match(self):
        """Test that None is returned when no rules match."""
        config = ToolApprovalConfig(
            always_deny=[],
            always_allow=[],
        )

        result = ApprovalMiddleware._check_approval_rules(
            config, "test_tool", {"query": "anything"}
        )

        assert result is None

    def test_check_approval_rules_deny_takes_precedence(self):
        """Test that deny rules take precedence over allow rules."""
        config = ToolApprovalConfig(
            always_deny=[ToolApprovalRule(name="test_tool", args=None)],
            always_allow=[ToolApprovalRule(name="test_tool", args=None)],
        )

        result = ApprovalMiddleware._check_approval_rules(config, "test_tool", {})

        assert result is False

    def test_check_approval_mode_bypass_semi_active(self):
        """Test that SEMI_ACTIVE mode never bypasses approval."""
        config = ToolApprovalConfig(always_deny=[], always_allow=[])

        result = ApprovalMiddleware._check_approval_mode_bypass(
            ApprovalMode.SEMI_ACTIVE, config, "test_tool", {}
        )

        assert result is False

    def test_check_approval_mode_bypass_active(self):
        """Test that ACTIVE mode bypasses unless explicitly denied."""
        config = ToolApprovalConfig(always_deny=[], always_allow=[])

        result = ApprovalMiddleware._check_approval_mode_bypass(
            ApprovalMode.ACTIVE, config, "test_tool", {}
        )

        assert result is True

    def test_check_approval_mode_bypass_active_with_deny(self):
        """Test that ACTIVE mode respects deny rules."""
        config = ToolApprovalConfig(
            always_deny=[ToolApprovalRule(name="test_tool", args=None)],
            always_allow=[],
        )

        result = ApprovalMiddleware._check_approval_mode_bypass(
            ApprovalMode.ACTIVE, config, "test_tool", {}
        )

        assert result is False

    def test_check_approval_mode_bypass_aggressive(self):
        """Test that AGGRESSIVE mode always bypasses approval."""
        config = ToolApprovalConfig(
            always_deny=[ToolApprovalRule(name="test_tool", args=None)],
            always_allow=[],
        )

        result = ApprovalMiddleware._check_approval_mode_bypass(
            ApprovalMode.AGGRESSIVE, config, "test_tool", {}
        )

        assert result is True

    def test_save_approval_decision_allow(self):
        """Test saving an allow decision."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.approval.json"
            config = ToolApprovalConfig(always_deny=[], always_allow=[])
            config.save_to_json_file(config_file)

            ApprovalMiddleware._save_approval_decision(
                config, config_file, "test_tool", {"query": "test"}, allow=True
            )

            # Reload config
            loaded_config = ToolApprovalConfig.from_json_file(config_file)
            assert len(loaded_config.always_allow) == 1
            assert loaded_config.always_allow[0].name == "test_tool"
            assert loaded_config.always_allow[0].args == {"query": "test"}

    def test_save_approval_decision_deny(self):
        """Test saving a deny decision."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.approval.json"
            config = ToolApprovalConfig(always_deny=[], always_allow=[])
            config.save_to_json_file(config_file)

            ApprovalMiddleware._save_approval_decision(
                config, config_file, "test_tool", {"query": "test"}, allow=False
            )

            loaded_config = ToolApprovalConfig.from_json_file(config_file)
            assert len(loaded_config.always_deny) == 1
            assert loaded_config.always_deny[0].name == "test_tool"

    def test_save_approval_decision_replaces_existing(self):
        """Test that saving a decision replaces existing rules."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.approval.json"
            config = ToolApprovalConfig(
                always_allow=[
                    ToolApprovalRule(name="test_tool", args={"query": "test"})
                ],
                always_deny=[],
            )
            config.save_to_json_file(config_file)

            # Save a deny decision for the same tool/args
            ApprovalMiddleware._save_approval_decision(
                config, config_file, "test_tool", {"query": "test"}, allow=False
            )

            loaded_config = ToolApprovalConfig.from_json_file(config_file)
            assert len(loaded_config.always_allow) == 0
            assert len(loaded_config.always_deny) == 1

    @pytest.mark.asyncio
    async def test_awrap_tool_call_with_allow(self, create_mock_tool):
        """Test that tool is executed when allowed."""
        middleware = ApprovalMiddleware()

        # Mock request
        mock_tool = create_mock_tool("test_tool")
        request = Mock(spec=ToolCallRequest)
        request.tool_call = {
            "id": "call_1",
            "name": "test_tool",
            "args": {"query": "test"},
        }
        request.tool = mock_tool
        request.runtime = Mock()
        request.runtime.context = AgentContext(
            approval_mode=ApprovalMode.AGGRESSIVE,
            working_dir=Path("/tmp"),
        )

        # Mock handler
        handler = AsyncMock(
            return_value=ToolMessage(
                name="test_tool",
                content="result",
                tool_call_id="call_1",
            )
        )

        result = await middleware.awrap_tool_call(request, handler)

        assert isinstance(result, ToolMessage)
        assert result.content == "result"
        handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_awrap_tool_call_with_deny(self, create_mock_tool):
        """Test that tool is not executed when denied."""
        with tempfile.TemporaryDirectory() as tmpdir:
            middleware = ApprovalMiddleware()

            # Create config with deny rule
            config_file = Path(tmpdir) / "config.approval.json"
            config = ToolApprovalConfig(
                always_deny=[ToolApprovalRule(name="test_tool", args=None)],
                always_allow=[],
            )
            config.save_to_json_file(config_file)

            mock_tool = create_mock_tool("test_tool")
            request = Mock(spec=ToolCallRequest)
            request.tool_call = {
                "id": "call_1",
                "name": "test_tool",
                "args": {"query": "test"},
            }
            request.tool = mock_tool
            request.runtime = Mock()
            request.runtime.context = AgentContext(
                approval_mode=ApprovalMode.SEMI_ACTIVE,
                working_dir=Path(tmpdir),
            )

            # Mock the interrupt to return DENY
            with patch("src.middleware.approval.interrupt", return_value=DENY):
                handler = AsyncMock()
                result = await middleware.awrap_tool_call(request, handler)

            assert isinstance(result, ToolMessage)
            assert getattr(result, "is_error", False) is True
            content = result.text
            assert "denied" in content.lower()
            handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_awrap_tool_call_with_exception(self, create_mock_tool):
        """Test that exceptions are caught and returned as error messages."""
        middleware = ApprovalMiddleware()

        mock_tool = create_mock_tool("test_tool")
        request = Mock(spec=ToolCallRequest)
        request.tool_call = {"id": "call_1", "name": "test_tool", "args": {}}
        request.tool = mock_tool
        request.runtime = Mock()
        request.runtime.context = AgentContext(
            approval_mode=ApprovalMode.AGGRESSIVE,
            working_dir=Path("/tmp"),
        )

        # Mock handler to raise exception
        handler = AsyncMock(side_effect=Exception("Test error"))

        result = await middleware.awrap_tool_call(request, handler)

        assert isinstance(result, ToolMessage)
        assert getattr(result, "is_error", False) is True
        content = result.text
        assert "Test error" in content


class TestFieldExtractor:
    """Tests for create_field_extractor helper."""

    def test_extract_single_field(self):
        """Test extracting a pattern from a single field."""
        extractor = create_field_extractor(
            {
                "command": r"(?P<command>\S+)",  # First word only
            }
        )

        result = extractor({"command": "echo hello world"})

        assert result["command"] == "echo"

    def test_extract_multiple_fields(self):
        """Test extracting patterns from multiple fields."""
        extractor = create_field_extractor(
            {
                "command": r"(?P<base_cmd>\S+)",
                "path": r"(?P<filename>[^/]+)$",
            }
        )

        result = extractor(
            {"command": "git commit -m 'message'", "path": "/home/user/file.txt"}
        )

        assert result["base_cmd"] == "git"
        assert result["filename"] == "file.txt"

    def test_no_match_keeps_original(self):
        """Test that fields without matches keep original values."""
        extractor = create_field_extractor(
            {
                "command": r"(?P<command>XYZ)",  # Won't match
            }
        )

        result = extractor({"command": "echo hello"})

        assert result["command"] == "echo hello"


class TestFieldTransformer:
    """Tests for create_field_transformer helper."""

    def test_transform_single_field(self):
        """Test transforming a single field."""
        transformer = create_field_transformer(
            {
                "command": lambda x: x.split()[0],
            }
        )

        result = transformer({"command": "echo hello world"})

        assert result["command"] == "echo"

    def test_transform_multiple_fields(self):
        """Test transforming multiple fields."""
        transformer = create_field_transformer(
            {
                "command": lambda x: x.upper(),
                "path": lambda x: x.replace("/", "_"),
            }
        )

        result = transformer({"command": "test", "path": "/home/user"})

        assert result["command"] == "TEST"
        assert result["path"] == "_home_user"

    def test_transform_handles_exceptions(self):
        """Test that transformation exceptions don't break the function."""
        transformer = create_field_transformer(
            {
                "command": lambda x: x.split()[10],  # Will raise IndexError
            }
        )

        result = transformer({"command": "echo"})

        # Should keep original value when transform fails
        assert result["command"] == "echo"
