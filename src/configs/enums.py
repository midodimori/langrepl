"""Enum types for configuration."""

from enum import Enum

__all__ = [
    "ApprovalMode",
    "CheckpointerProvider",
    "LLMProvider",
    "SandboxPermission",
    "SandboxType",
]


class LLMProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    OLLAMA = "ollama"
    LMSTUDIO = "lmstudio"
    BEDROCK = "bedrock"
    DEEPSEEK = "deepseek"
    ZHIPUAI = "zhipuai"


class CheckpointerProvider(str, Enum):
    SQLITE = "sqlite"
    MEMORY = "memory"


class ApprovalMode(str, Enum):
    """Tool approval mode for interactive sessions."""

    SEMI_ACTIVE = "semi-active"  # No effect (default)
    ACTIVE = "active"  # Bypass all approval rules except "always_deny"
    AGGRESSIVE = "aggressive"  # Bypass all approval rules


class SandboxType(str, Enum):
    """Sandbox backend types."""

    BUBBLEWRAP = "bubblewrap"
    SEATBELT = "seatbelt"


class SandboxPermission(str, Enum):
    """Permissions that can be granted to sandboxed tools."""

    NETWORK = "network"
    FILESYSTEM = "filesystem"
