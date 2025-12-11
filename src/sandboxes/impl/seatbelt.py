"""Seatbelt-based sandbox for macOS."""

from __future__ import annotations

import os
import shutil
import tempfile
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from src.core.config import SandboxPermission
from src.sandboxes.base import Sandbox

if TYPE_CHECKING:
    from src.core.config import SandboxConfig

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
    """Generate a Seatbelt profile string based on config."""
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

    # Literal paths for path resolution
    for path in PATH_RESOLUTION_LITERALS:
        escaped = _escape_seatbelt_path(path)
        rules.append(f'(allow file-read* (literal "{escaped}"))')

    # Read-only paths from config
    for path in config.read_paths:
        escaped = _escape_seatbelt_path(os.path.expanduser(path))
        rules.append(f'(allow file-read* (subpath "{escaped}"))')

    # Write paths from config (includes read access)
    for path in config.write_paths:
        escaped = _escape_seatbelt_path(os.path.expanduser(path))
        rules.append(f'(allow file-read* (subpath "{escaped}"))')
        rules.append(f'(allow file-write* (subpath "{escaped}"))')
    # Use provided permissions or fall back to config
    effective_perms = permissions if permissions is not None else config.permissions

    # Always allow Unix domain sockets (local IPC only, not real network)
    # This enables Docker, OrbStack, and other local socket-based tools
    rules.append("(allow network* (local unix-socket))")

    if SandboxPermission.NETWORK in effective_perms:
        rules.extend(
            [
                "(allow network-outbound)",
                "(allow network-inbound)",
                "(allow system-socket)",
            ]
        )

    if SandboxPermission.FILESYSTEM in effective_perms and working_dir:
        escaped = _escape_seatbelt_path(str(working_dir))
        rules.append(f'(allow file-read* (subpath "{escaped}"))')
        rules.append(f'(allow file-write* (subpath "{escaped}"))')

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
