"""Bubblewrap-based sandbox for Linux."""

from __future__ import annotations

import os
import shutil

from src.core.config import SandboxPermission
from src.sandboxes.base import Sandbox


class BubblewrapSandbox(Sandbox):
    """Executes tools inside a bubblewrap sandbox (Linux only)."""

    sandbox_name = "bubblewrap"

    @classmethod
    def is_available(cls) -> bool:
        """Check if bubblewrap is available."""
        import platform

        if platform.system() != "Linux":
            return False
        return shutil.which("bwrap") is not None

    def _build_bwrap_args(
        self, permissions: list[SandboxPermission] | None = None
    ) -> list[str]:
        """Build common bwrap arguments from config."""
        effective_perms = (
            permissions if permissions is not None else self.config.permissions
        )

        bwrap_args = [
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--tmpfs",
            "/tmp",
        ]

        for path in self.config.read_paths:
            expanded = os.path.expanduser(path)
            bwrap_args.extend(["--ro-bind-try", expanded, expanded])

        for path in self.config.write_paths:
            expanded = os.path.expanduser(path)
            bwrap_args.extend(["--bind-try", expanded, expanded])

        if SandboxPermission.FILESYSTEM in effective_perms:
            bwrap_args.extend(["--bind", str(self.working_dir), str(self.working_dir)])

        if SandboxPermission.NETWORK not in effective_perms:
            bwrap_args.append("--unshare-net")

        return bwrap_args

    def _build_sandbox_command(
        self,
        permissions: list[SandboxPermission],
    ) -> list[str]:
        """Build bubblewrap command prefix."""
        bwrap_args = self._build_bwrap_args(permissions=permissions)

        if SandboxPermission.FILESYSTEM in permissions:
            bwrap_args.extend(
                ["--setenv", "LANGREPL_WORKING_DIR", str(self.working_dir)]
            )

        bwrap_args.append("--unshare-pid")
        return ["bwrap", *bwrap_args]

    def _build_mcp_wrapper(
        self,
        command: str,
        args: list[str],
        permissions: list[SandboxPermission],
    ) -> tuple[str, list[str]]:
        """Build bubblewrap MCP wrapper."""
        bwrap_args = self._build_bwrap_args(permissions=permissions)
        bwrap_args.append("--unshare-pid")
        resolved_command = shutil.which(command) or command
        bwrap_args.extend(["--", resolved_command] + args)
        return "bwrap", bwrap_args
