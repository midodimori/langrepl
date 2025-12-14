"""Tool approval configuration models."""

import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

__all__ = [
    "ToolApprovalConfig",
    "ToolApprovalRule",
]


class ToolApprovalRule(BaseModel):
    """Rule for approving/denying specific tool calls"""

    name: str
    args: dict[str, Any] | None = None

    def matches_call(self, tool_name: str, tool_args: dict[str, Any]) -> bool:
        """Check if this rule matches a specific tool call"""
        if self.name != tool_name:
            return False

        # If no args specified, match any call to this tool
        if not self.args:
            return True

        # Check argument matches (exact or regex)
        for key, expected_value in self.args.items():
            if key not in tool_args:
                return False

            actual_value = str(tool_args[key])
            expected_str = str(expected_value)

            # Try exact match first (safer and more intuitive)
            if actual_value == expected_str:
                continue

            try:
                pattern = re.compile(expected_str)
                if pattern.fullmatch(actual_value):
                    continue
            except re.error:
                # Not a valid regex, already failed exact match above
                pass

            # No match found
            return False

        return True


class ToolApprovalConfig(BaseModel):
    """Configuration for tool approvals and denials"""

    always_allow: list[ToolApprovalRule] = Field(default_factory=list)
    always_deny: list[ToolApprovalRule] = Field(default_factory=list)

    @classmethod
    def from_json_file(cls, file_path: Path) -> "ToolApprovalConfig":
        """Load configuration from JSON file"""
        if not file_path.exists():
            return cls()

        try:
            with open(file_path) as f:
                content = f.read()
            return cls.model_validate_json(content)
        except Exception:
            return cls()

    def save_to_json_file(self, file_path: Path):
        """Save configuration to JSON file"""
        file_path.parent.mkdir(exist_ok=True)
        with open(file_path, "w") as f:
            f.write(self.model_dump_json(indent=2))
