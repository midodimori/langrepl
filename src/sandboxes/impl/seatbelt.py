"""Seatbelt-based sandbox for macOS."""

from __future__ import annotations

import os
import shutil
import tempfile
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from src.configs import SandboxPermission
from src.sandboxes.base import Sandbox

if TYPE_CHECKING:
    from src.configs import SandboxConfig

# Paths needed for macOS path resolution (literal access to traverse directories)
PATH_RESOLUTION_LITERALS = [
    "/",
    "/opt",
    "/var",
    "/private",
    "/private/var",
    "/private/var/select",
    "/Users",
]


def _escape_seatbelt_path(path: str) -> str:
    """Escape special characters for seatbelt profile string literals."""
    return (
        path.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "")
        .replace("\r", "")
    )


def generate_seatbelt_profile(
    config: SandboxConfig,
    working_dir: Path | None = None,
    allow_ipc: bool = False,
    permissions: list[SandboxPermission] | None = None,
) -> str:
    """Generate a Seatbelt profile string based on config.

    Permission model:
    - execution_paths: Always allowed (needed for execution - system libs, binaries)
    - unix sockets: Always allowed (needed for Docker daemon communication)
    - FILESYSTEM: Enables filesystem_paths + working_dir write access
    - NETWORK: Enables TCP/IP (Docker containers isolated via --network none injection)
    """
    rules = [
        "(version 1)",
        "(deny default)",
        "(allow process-fork)",
        "(allow process-exec)",
        "(allow process-exec-interpreter)",
        "(allow signal (target self))",
        "(allow mach-lookup)",
        "(allow sysctl-read)",
        '(allow file-write* (literal "/dev/null"))',
    ]

    if allow_ipc:
        rules.extend(
            [
                "(allow ipc-posix-shm-read-data)",
                "(allow ipc-posix-shm-write-data)",
            ]
        )

    # Literal paths for path resolution (always needed)
    for path in PATH_RESOLUTION_LITERALS:
        escaped = _escape_seatbelt_path(path)
        rules.append(f'(allow file-read* (literal "{escaped}"))')

    # Execution paths from config (always allowed - needed for execution)
    for path in config.execution_paths:
        escaped = _escape_seatbelt_path(os.path.expanduser(path))
        rules.append(f'(allow file-read* (subpath "{escaped}"))')

    # Use provided permissions or fall back to config
    effective_perms = permissions if permissions is not None else config.permissions

    # FILESYSTEM permission: enables filesystem_paths + working_dir
    if SandboxPermission.FILESYSTEM in effective_perms:
        for path in config.filesystem_paths:
            escaped = _escape_seatbelt_path(os.path.expanduser(path))
            rules.append(f'(allow file-read* (subpath "{escaped}"))')
            rules.append(f'(allow file-write* (subpath "{escaped}"))')
        if working_dir:
            escaped = _escape_seatbelt_path(str(working_dir))
            rules.append(f'(allow file-read* (subpath "{escaped}"))')
            rules.append(f'(allow file-write* (subpath "{escaped}"))')

    # Always allow unix sockets (needed for Docker daemon communication)
    # Network isolation for Docker containers is handled by injecting --network none
    rules.append("(allow network* (local unix-socket))")

    # NETWORK permission: enables TCP/IP
    if SandboxPermission.NETWORK in effective_perms:
        rules.extend(
            [
                "(allow network-outbound)",
                "(allow network-inbound)",
                "(allow system-socket)",
            ]
        )

    return "\n".join(rules)


def _write_temp_profile(content: str, suffix: str = ".sb") -> str:
    """Write profile content to a temporary file."""
    fd, path = tempfile.mkstemp(suffix=suffix, prefix="sandbox_")
    try:
        os.write(fd, content.encode())
    finally:
        os.close(fd)
    return path


class SeatbeltSandbox(Sandbox):
    """Executes tools inside a macOS sandbox using sandbox-exec."""

    sandbox_name = "seatbelt"

    def __init__(self, config: SandboxConfig, working_dir: Path):
        super().__init__(config, working_dir)
        self._mcp_profiles: list[str] = []
        self._tool_profile: str | None = None
        self._lock = threading.Lock()  # Protect profile state from race conditions

    def _create_profile(
        self,
        allow_ipc: bool = False,
        permissions: list[SandboxPermission] | None = None,
        for_mcp: bool = False,
    ) -> str:
        """Create a temp profile file (thread-safe)."""
        content = generate_seatbelt_profile(
            self.config, self.working_dir, allow_ipc, permissions=permissions
        )
        path = _write_temp_profile(content)
        with self._lock:
            if for_mcp:
                self._mcp_profiles.append(path)
            else:
                # Clean up previous tool profile to prevent temp file leaks
                if self._tool_profile:
                    try:
                        os.unlink(self._tool_profile)
                    except Exception:
                        pass
                self._tool_profile = path
        return path

    def cleanup(self) -> None:
        """Remove all temp profile files (thread-safe)."""
        with self._lock:
            if self._tool_profile:
                try:
                    os.unlink(self._tool_profile)
                except Exception:
                    pass
                self._tool_profile = None
            for path in self._mcp_profiles:
                try:
                    os.unlink(path)
                except Exception:
                    pass
            self._mcp_profiles.clear()

    @classmethod
    def is_available(cls) -> bool:
        """Check if sandbox-exec is available."""
        import platform

        if platform.system() != "Darwin":
            return False
        return shutil.which("sandbox-exec") is not None

    def _build_sandbox_command(
        self,
        permissions: list[SandboxPermission],
    ) -> list[str]:
        """Build seatbelt command prefix."""
        profile_path = self._create_profile(allow_ipc=True, permissions=permissions)
        return ["sandbox-exec", "-f", profile_path]

    def _build_mcp_wrapper(
        self,
        command: str,
        args: list[str],
        permissions: list[SandboxPermission],
    ) -> tuple[str, list[str]]:
        """Build seatbelt MCP wrapper."""
        profile_path = self._create_profile(permissions=permissions, for_mcp=True)
        return "sandbox-exec", ["-f", profile_path, command] + args
