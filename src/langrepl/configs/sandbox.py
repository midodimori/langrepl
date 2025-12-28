"""Sandbox configuration classes."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from langrepl.configs.base import VersionedConfig
from langrepl.configs.utils import _load_dir_items, _validate_no_duplicates
from langrepl.core.constants import PLATFORM, SANDBOX_CONFIG_VERSION


class SandboxType(str, Enum):
    """Sandbox backend type."""

    SEATBELT = "seatbelt"
    BUBBLEWRAP = "bubblewrap"


class SandboxOS(str, Enum):
    """Target operating system for sandbox."""

    MACOS = "macos"
    LINUX = "linux"


class FilesystemConfig(BaseModel):
    """Filesystem access rules for sandbox."""

    read: list[str] = Field(
        default_factory=list,
        description="Paths allowed for reading (include '.' for working_dir)",
    )
    write: list[str] = Field(
        default_factory=list,
        description="Paths allowed for writing (include '.' for working_dir)",
    )
    hidden: list[str] = Field(
        default_factory=list,
        description="Paths/patterns to hide from sandbox (supports glob: ~/.ssh, *.pem)",
    )


class NetworkConfig(BaseModel):
    """Network access rules for sandbox.

    NOTE: Domain-specific filtering requires a proxy server
    which is not yet implemented. Currently, network access is binary:
    - If `remote` is empty: all outbound network access is blocked
    - If `remote` contains any value (including "*"): all outbound TCP is allowed

    The domain patterns are stored for future proxy-based filtering implementation.
    """

    remote: list[str] = Field(
        default_factory=list,
        description="Allowed remote hosts. Currently only '*' (allow all) or empty (deny all) are enforced.",
    )
    local: list[str] = Field(
        default_factory=list, description="Allowed local unix sockets"
    )


class SandboxConfig(VersionedConfig):
    """Configuration for a sandbox profile."""

    version: str = Field(default=SANDBOX_CONFIG_VERSION)
    name: str = Field(description="Unique sandbox profile name")
    type: SandboxType = Field(description="Sandbox backend type")
    os: SandboxOS = Field(description="Target operating system")
    filesystem: FilesystemConfig = Field(default_factory=FilesystemConfig)
    network: NetworkConfig = Field(default_factory=NetworkConfig)

    @classmethod
    def get_latest_version(cls) -> str:
        return SANDBOX_CONFIG_VERSION

    @model_validator(mode="after")
    def validate_os_compatibility(self) -> SandboxConfig:
        """Validate that sandbox type matches OS."""
        if self.type == SandboxType.SEATBELT and self.os != SandboxOS.MACOS:
            raise ValueError("seatbelt sandbox type requires os: macos")
        if self.type == SandboxType.BUBBLEWRAP and self.os != SandboxOS.LINUX:
            raise ValueError("bubblewrap sandbox type requires os: linux")
        return self

    def validate_current_os(self) -> None:
        """Validate sandbox is compatible with current OS.

        Raises:
            RuntimeError: If sandbox OS doesn't match current platform
        """
        current_os = SandboxOS.MACOS if PLATFORM == "Darwin" else SandboxOS.LINUX
        if self.os != current_os:
            raise RuntimeError(
                f"Sandbox '{self.name}' requires {self.os.value}, "
                f"but running on {current_os.value}"
            )


class SandboxProfileBinding(BaseModel):
    """Binds patterns to a sandbox profile."""

    sandbox: SandboxConfig | None = Field(
        default=None, description="Sandbox config (None for no-sandbox)"
    )
    patterns: list[str] = Field(description="Tool patterns to match")


class AgentSandboxConfig(BaseModel):
    """Agent-level sandbox configuration."""

    enabled: bool = Field(default=False, description="Enable sandboxing for this agent")
    profiles: list[SandboxProfileBinding] = Field(
        default_factory=list, description="Profile bindings"
    )


class BatchSandboxConfig(BaseModel):
    """Batch configuration for sandbox profiles."""

    sandboxes: list[SandboxConfig] = Field(default_factory=list)

    @property
    def sandbox_names(self) -> list[str]:
        return [s.name for s in self.sandboxes]

    def get_sandbox_config(self, name: str) -> SandboxConfig | None:
        return next((s for s in self.sandboxes if s.name == name), None)

    @classmethod
    async def from_yaml(
        cls,
        dir_path: Path | None = None,
    ) -> BatchSandboxConfig:
        """Load sandbox configurations from directory."""
        sandboxes = []
        if dir_path and dir_path.exists():
            sandboxes.extend(
                await _load_dir_items(
                    dir_path,
                    key="name",
                    config_type="Sandbox",
                    config_class=SandboxConfig,
                )
            )

        if sandboxes:
            _validate_no_duplicates(sandboxes, key="name", config_type="Sandbox")

        validated = [SandboxConfig.model_validate(s) for s in sandboxes]
        return cls(sandboxes=validated)
