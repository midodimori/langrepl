"""Bubblewrap-based sandbox for Linux."""

from __future__ import annotations

import os
import shutil

from src.configs import SandboxPermission
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
        """Build common bwrap arguments from config.

        Permission model:
        - execution_ro_paths: Always read-only (system libs, binaries)
        - execution_rw_paths: Always read-write (npm cache, uv cache)
        - FILESYSTEM: Enables filesystem_paths + working_dir write access
        - NETWORK: Enables network access (without it, --unshare-net is applied)
        """
        effective_perms = (
            permissions if permissions is not None else self.config.permissions
        )

        bwrap_args = [
            "--proc",
            "/proc",
            "--dev",
            "/dev",
        ]

        # Read-only execution paths (always allowed - needed for execution)
        for path in self.config.execution_ro_paths:
            expanded = os.path.expanduser(path)
            bwrap_args.extend(["--ro-bind-try", expanded, expanded])

        # Read-write execution paths (always allowed - npm cache, uv cache, etc.)
        for path in self.config.execution_rw_paths:
            expanded = os.path.expanduser(path)
            bwrap_args.extend(["--bind-try", expanded, expanded])

        # FILESYSTEM permission: enables filesystem_paths + working_dir
        if SandboxPermission.FILESYSTEM in effective_perms:
            for path in self.config.filesystem_paths:
                expanded = os.path.expanduser(path)
                # /tmp gets special handling: use tmpfs with size limit
                if expanded == "/tmp":
                    bwrap_args.extend(["--tmpfs", "/tmp:size=64M"])
                else:
                    bwrap_args.extend(["--bind-try", expanded, expanded])
            bwrap_args.extend(["--bind", str(self.working_dir), str(self.working_dir)])

        # NETWORK permission: without it, isolate network namespace
        if SandboxPermission.NETWORK not in effective_perms:
            bwrap_args.append("--unshare-net")

        # Unix socket access (opt-in via socket_paths for Docker, etc.)
        for socket_path in self.config.socket_paths:
            expanded = os.path.expanduser(socket_path)
            bwrap_args.extend(["--bind-try", expanded, expanded])

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
