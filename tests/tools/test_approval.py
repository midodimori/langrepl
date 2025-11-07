from src.core.config import ApprovalMode, ToolApprovalConfig, ToolApprovalRule
from src.middleware.approval import (
    ApprovalMiddleware,
    create_field_extractor,
    create_field_transformer,
)


class TestCheckApproval:
    def test_always_deny_takes_priority(self):
        config = ToolApprovalConfig(
            always_allow=[ToolApprovalRule(name="read_file", args=None)],
            always_deny=[ToolApprovalRule(name="read_file", args={"path": "/tmp/.*"})],
        )

        result = ApprovalMiddleware._check_approval_rules(
            config, "read_file", {"path": "/tmp/test"}
        )
        assert result is False

    def test_always_allow_when_no_deny(self):
        config = ToolApprovalConfig(
            always_allow=[ToolApprovalRule(name="read_file", args=None)], always_deny=[]
        )

        result = ApprovalMiddleware._check_approval_rules(
            config, "read_file", {"path": "/any/path"}
        )
        assert result is True

    def test_no_match_returns_none(self):
        config = ToolApprovalConfig(
            always_allow=[ToolApprovalRule(name="write_file", args=None)],
            always_deny=[],
        )

        result = ApprovalMiddleware._check_approval_rules(
            config, "read_file", {"path": "/tmp/test"}
        )
        assert result is None

    def test_empty_config_returns_none(self):
        config = ToolApprovalConfig(always_allow=[], always_deny=[])
        result = ApprovalMiddleware._check_approval_rules(
            config, "read_file", {"path": "/tmp/test"}
        )
        assert result is None

    def test_deny_overrides_allow_same_tool(self):
        config = ToolApprovalConfig(
            always_allow=[ToolApprovalRule(name="read_file", args=None)],
            always_deny=[
                ToolApprovalRule(name="read_file", args={"path": "/etc/passwd"})
            ],
        )

        result = ApprovalMiddleware._check_approval_rules(
            config, "read_file", {"path": "/etc/passwd"}
        )
        assert result is False

        result = ApprovalMiddleware._check_approval_rules(
            config, "read_file", {"path": "/tmp/safe"}
        )
        assert result is True


class TestCheckApprovalModeBypass:
    def test_semi_active_never_bypasses(self):
        config = ToolApprovalConfig(always_allow=[], always_deny=[])
        result = ApprovalMiddleware._check_approval_mode_bypass(
            ApprovalMode.SEMI_ACTIVE, config, "any_tool", {}
        )
        assert result is False

    def test_active_bypasses_except_always_deny(self):
        config = ToolApprovalConfig(
            always_allow=[],
            always_deny=[ToolApprovalRule(name="dangerous_tool", args=None)],
        )

        result = ApprovalMiddleware._check_approval_mode_bypass(
            ApprovalMode.ACTIVE, config, "safe_tool", {}
        )
        assert result is True

        result = ApprovalMiddleware._check_approval_mode_bypass(
            ApprovalMode.ACTIVE, config, "dangerous_tool", {}
        )
        assert result is False

    def test_aggressive_bypasses_everything(self):
        config = ToolApprovalConfig(
            always_allow=[],
            always_deny=[ToolApprovalRule(name="dangerous_tool", args=None)],
        )

        result = ApprovalMiddleware._check_approval_mode_bypass(
            ApprovalMode.AGGRESSIVE, config, "dangerous_tool", {}
        )
        assert result is True

        result = ApprovalMiddleware._check_approval_mode_bypass(
            ApprovalMode.AGGRESSIVE, config, "any_tool", {}
        )
        assert result is True


class TestCreateFieldExtractor:
    def test_extract_single_field(self):
        extractor = create_field_extractor({"command": r"(?P<command>\S+)"})
        result = extractor({"command": "git status --verbose"})
        assert result["command"] == "git"

    def test_extract_multiple_fields(self):
        extractor = create_field_extractor(
            {"path": r"(?P<filename>[^/]+)$", "mode": r"(?P<mode>\w+)"}
        )
        result = extractor({"path": "/tmp/test/file.txt", "mode": "read"})
        assert result["filename"] == "file.txt"
        assert result["mode"] == "read"

    def test_no_match_keeps_original(self):
        extractor = create_field_extractor({"command": r"(?P<cmd>nomatch)"})
        result = extractor({"command": "git status"})
        assert result["command"] == "git status"

    def test_field_not_in_args(self):
        extractor = create_field_extractor({"missing": r"(?P<value>\w+)"})
        result = extractor({"command": "test"})
        assert result == {"command": "test"}


class TestCreateFieldTransformer:
    def test_transform_single_field(self):
        transformer = create_field_transformer({"command": lambda x: x.split()[0]})
        result = transformer({"command": "git status --verbose"})
        assert result["command"] == "git"

    def test_transform_multiple_fields(self):
        import os

        transformer = create_field_transformer(
            {"path": lambda x: os.path.basename(x), "name": lambda x: x.upper()}
        )
        result = transformer({"path": "/tmp/test/file.txt", "name": "alice"})
        assert result["path"] == "file.txt"
        assert result["name"] == "ALICE"

    def test_transform_error_keeps_original(self):
        def int_to_str(x: str) -> str:
            return str(int(x))

        transformer = create_field_transformer({"value": int_to_str})
        result = transformer({"value": "not_a_number"})
        assert result["value"] == "not_a_number"

    def test_field_not_in_args(self):
        transformer = create_field_transformer({"missing": lambda x: x.upper()})
        result = transformer({"command": "test"})
        assert result == {"command": "test"}
