"""Factory for creating sandbox executor instances."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from src.configs import SandboxType
from src.sandboxes.base import Sandbox

if TYPE_CHECKING:
    from src.configs import SandboxConfig


class SandboxFactory:
    """Factory for creating sandbox executor instances."""

    @staticmethod
    def create(config: SandboxConfig, working_dir: Path) -> Sandbox:
        """Create sandbox executor based on config type.

        Raises:
            ValueError: If sandbox type is unknown.
            RuntimeError: If sandbox backend is not available on this system.
        """
        if config.type == SandboxType.BUBBLEWRAP:
            from src.sandboxes.impl.bubblewrap import BubblewrapSandbox

            if not BubblewrapSandbox.is_available():
                raise RuntimeError(
                    "Bubblewrap sandbox is not available. "
                    "Install with: sudo apt install bubblewrap"
                )
            return BubblewrapSandbox(config, working_dir)

        if config.type == SandboxType.SEATBELT:
            from src.sandboxes.impl.seatbelt import SeatbeltSandbox

            if not SeatbeltSandbox.is_available():
                raise RuntimeError(
                    "Seatbelt sandbox is not available. "
                    "Requires macOS with sandbox-exec."
                )
            return SeatbeltSandbox(config, working_dir)

        raise ValueError(f"Unknown sandbox type: {config.type}")
