"""Sandbox configuration models."""

from pathlib import Path

from pydantic import BaseModel, Field

from src.configs.base import (
    VersionedConfig,
    _load_dir_items,
    _validate_no_duplicates,
)
from src.configs.enums import SandboxPermission, SandboxType
from src.core.constants import (
    CONFIG_SANDBOXES_DIR,
    DEFAULT_SANDBOX_TIMEOUT,
    SANDBOX_CONFIG_VERSION,
)

__all__ = [
    "BatchSandboxConfig",
    "SandboxConfig",
]


class SandboxConfig(VersionedConfig):
    """Configuration for sandbox execution."""

    version: str = Field(
        default=SANDBOX_CONFIG_VERSION, description="Config schema version"
    )
    name: str = Field(description="Sandbox configuration name")
    type: SandboxType = Field(description="Sandbox backend type")
    permissions: list[SandboxPermission] = Field(
        default_factory=list,
        description="Permissions granted to sandboxed tools",
    )
    execution_ro_paths: list[str] = Field(
        default_factory=list,
        description="Paths always mounted read-only (system libs, binaries)",
    )
    execution_rw_paths: list[str] = Field(
        default_factory=list,
        description="Paths always mounted read-write (npm cache, uv cache)",
    )
    filesystem_paths: list[str] = Field(
        default_factory=list,
        description="Additional paths for read-write when FILESYSTEM permission granted",
    )
    socket_paths: list[str] = Field(
        default_factory=list,
        description="Unix socket paths to allow (e.g., Docker, OrbStack, Rancher)",
    )

    timeout: float = Field(
        default=DEFAULT_SANDBOX_TIMEOUT,
        ge=1.0,
        le=3600.0,
        description="Timeout in seconds for sandbox tool execution (1-3600)",
    )

    @classmethod
    def get_latest_version(cls) -> str:
        return SANDBOX_CONFIG_VERSION

    def has_permission(self, permission: SandboxPermission) -> bool:
        """Check if a permission is granted."""
        return permission in self.permissions


class BatchSandboxConfig(BaseModel):
    """Batch container for sandbox configurations."""

    sandboxes: list[SandboxConfig] = Field(
        default_factory=list, description="The sandbox configurations"
    )

    @property
    def sandbox_names(self) -> list[str]:
        return [sb.name for sb in self.sandboxes]

    def get_sandbox_config(self, sandbox_name: str) -> SandboxConfig | None:
        return next((sb for sb in self.sandboxes if sb.name == sandbox_name), None)

    @classmethod
    async def from_yaml(
        cls,
        working_dir: Path,
    ) -> "BatchSandboxConfig":
        """Load sandbox configurations from YAML files in directory."""
        sandboxes = []
        dir_path = working_dir / CONFIG_SANDBOXES_DIR

        if dir_path.exists():
            sandboxes.extend(
                await _load_dir_items(
                    dir_path,
                    key="name",
                    config_type="Sandbox",
                    config_class=SandboxConfig,
                    working_dir=working_dir,
                )
            )

        _validate_no_duplicates(sandboxes, key="name", config_type="Sandbox")
        return cls.model_validate({"sandboxes": sandboxes})
