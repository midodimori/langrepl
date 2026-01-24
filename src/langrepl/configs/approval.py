"""Tool approval configuration classes."""

from __future__ import annotations

import re
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ApprovalMode(str, Enum):
    """Tool approval mode for interactive sessions."""

    SEMI_ACTIVE = "semi-active"  # No effect (default)
    ACTIVE = "active"  # Bypass all approval rules except "always_deny"
    AGGRESSIVE = "aggressive"  # Bypass all approval rules


class ToolApprovalRule(BaseModel):
    """Rule for approving/denying specific tool calls"""

    name: str
    args: dict[str, Any] | None = None

    def matches_call(self, tool_name: str, tool_args: dict[str, Any]) -> bool:
        """Check if this rule matches a specific tool call"""
        if self.name != tool_name:
            return False

        if not self.args:
            return True

        for key, expected_value in self.args.items():
            if key not in tool_args:
                return False

            actual_value = str(tool_args[key])
            expected_str = str(expected_value)

            if actual_value == expected_str:
                continue

            try:
                pattern = re.compile(expected_str)
                if pattern.fullmatch(actual_value):
                    continue
            except re.error:
                pass

            return False

        return True


def _default_always_ask_rules() -> list[ToolApprovalRule]:
    """Default rules for critical commands that always require approval."""
    return [
        ToolApprovalRule(name="run_command", args={"command": r"rm\s+-rf.*"}),
        ToolApprovalRule(name="run_command", args={"command": r"git\s+push.*"}),
        ToolApprovalRule(
            name="run_command", args={"command": r"git\s+reset\s+--hard.*"}
        ),
        ToolApprovalRule(name="run_command", args={"command": r"sudo\s+.*"}),
    ]


class ToolApprovalConfig(BaseModel):
    """Configuration for tool approvals and denials"""

    always_allow: list[ToolApprovalRule] = Field(default_factory=list)
    always_deny: list[ToolApprovalRule] = Field(default_factory=list)
    always_ask: list[ToolApprovalRule] = Field(default_factory=list)

    @classmethod
    def from_json_file(cls, file_path: Path) -> ToolApprovalConfig:
        """Load configuration from JSON file"""
        if not file_path.exists():
            config = cls(always_ask=_default_always_ask_rules())
            config.save_to_json_file(file_path)
            return config

        try:
            import json

            with open(file_path) as f:
                raw = json.load(f)

            if "always_ask" not in raw:
                raw["always_ask"] = [
                    r.model_dump() for r in _default_always_ask_rules()
                ]
                with open(file_path, "w") as f:
                    json.dump(raw, f, indent=2)

            return cls.model_validate(raw)
        except Exception:
            return cls()

    def save_to_json_file(self, file_path: Path) -> None:
        """Save configuration to JSON file"""
        file_path.parent.mkdir(exist_ok=True)
        with open(file_path, "w") as f:
            f.write(self.model_dump_json(indent=2))
