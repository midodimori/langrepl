"""Factory for creating sandbox backends."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from langrepl.configs.sandbox import SandboxType
from langrepl.core.constants import CONFIG_SANDBOX_CACHE_DIR
from langrepl.core.logging import get_logger
from langrepl.sandboxes.backends.base import SandboxBinding
from langrepl.sandboxes.backends.bubblewrap import BubblewrapBackend
from langrepl.sandboxes.backends.seatbelt import SeatbeltBackend

logger = get_logger(__name__)

if TYPE_CHECKING:
    from langrepl.configs.sandbox import AgentSandboxConfig, SandboxConfig
    from langrepl.sandboxes.backends.base import SandboxBackend

BACKEND_TYPES = {
    SandboxType.SEATBELT: SeatbeltBackend,
    SandboxType.BUBBLEWRAP: BubblewrapBackend,
}


class SandboxFactory:
    """Factory for creating sandbox backend instances."""

    def __init__(self) -> None:
        self._backends: dict[str, SandboxBackend] = {}

    def create_backend(
        self, config: SandboxConfig, working_dir: Path
    ) -> SandboxBackend:
        """Create backend for config."""
        if (cache_key := f"{config.name}:{working_dir}") in self._backends:
            return self._backends[cache_key]

        config.validate_current_os()

        if not (backend_cls := BACKEND_TYPES.get(config.type)):
            raise ValueError(f"Unknown sandbox type: {config.type}")

        cache_dir = working_dir / CONFIG_SANDBOX_CACHE_DIR
        backend = backend_cls(config, working_dir, cache_dir=cache_dir)
        backend.validate_environment()
        backend.warn_symlink_issues()
        self._backends[cache_key] = backend
        return backend

    def build_bindings(
        self, agent_config: AgentSandboxConfig, working_dir: Path
    ) -> list[SandboxBinding]:
        """Build sandbox bindings from agent config profiles."""
        if not agent_config or not agent_config.enabled:
            return []

        bindings = []
        for profile in agent_config.profiles:
            if profile.sandbox is None:
                backend = None
            else:
                backend = self.create_backend(profile.sandbox, working_dir)
            bindings.append(SandboxBinding(patterns=profile.patterns, backend=backend))

        return bindings
