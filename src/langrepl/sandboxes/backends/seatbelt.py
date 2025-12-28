"""macOS seatbelt (sandbox-exec) backend."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from langrepl.core.constants import PLATFORM
from langrepl.sandboxes.backends.base import SandboxBackend
from langrepl.sandboxes.constants import (
    SEATBELT_BSD_PROFILE,
    SEATBELT_MACH_SERVICES,
    SEATBELT_MDNS_RESPONDER_PATH,
)
from langrepl.utils.path import expand_pattern, pattern_to_regex

if TYPE_CHECKING:
    from langrepl.configs.sandbox import SandboxConfig


class SeatbeltBackend(SandboxBackend):
    """macOS sandbox-exec implementation."""

    def __init__(
        self, config: SandboxConfig, working_dir: Path, cache_dir: Path | None = None
    ):
        super().__init__(config, working_dir, cache_dir)
        self._profile_path: Path | None = None

    def validate_environment(self) -> None:
        if PLATFORM != "Darwin":
            raise RuntimeError(
                f"Seatbelt sandbox requires macOS, current platform: {PLATFORM}"
            )
        if not shutil.which("sandbox-exec"):
            raise RuntimeError("sandbox-exec not found in PATH")

    def build_command(
        self, command: list[str], extra_env: dict[str, str] | None = None
    ) -> list[str]:
        """Build complete sandbox-exec command."""
        profile_path = self._get_profile_path()
        env_args = self._build_env_args(extra_env)
        return env_args + ["sandbox-exec", "-f", str(profile_path)] + command

    def _build_env_args(self, extra_env: dict[str, str] | None = None) -> list[str]:
        """Build environment variable arguments."""
        args = ["env", "-i"]
        for key, value in self.get_sandbox_env().items():
            args.append(f"{key}={value}")
        if extra_env:
            for key, value in extra_env.items():
                args.append(f"{key}={value}")
        if tmpdir := os.environ.get("TMPDIR"):
            args.append(f"TMPDIR={tmpdir}")
        return args

    def _build_read_rules(self, pattern: str) -> list[str]:
        """Build read rules for a pattern."""
        if pattern.startswith("/dev/"):
            return [f'(allow file-read* (literal "{pattern}"))']

        rules = []
        seen: set[str] = set()
        working_dir_denied = "." not in self.config.filesystem.read
        for resolved in expand_pattern(pattern, self.working_dir):
            resolved_str = str(resolved)
            if resolved_str in seen:
                continue
            seen.add(resolved_str)
            if self._is_safe_path(resolved):
                rules.append(f'(allow file-read* (subpath "{resolved}"))')
                if working_dir_denied and resolved_str.startswith(
                    str(self.working_dir)
                ):
                    rules.append(f'(allow file-read-data (subpath "{resolved}"))')
        return rules

    def _build_write_rules(self, pattern: str) -> tuple[list[str], list[str]]:
        """Build write rules for a pattern. Returns (subpath_rules, literal_rules)."""
        if pattern == ".":
            return [f'(allow file-write* (subpath "{self.working_dir}"))'], []
        if pattern.startswith("/dev/"):
            return [], [f'(allow file-write* (literal "{pattern}"))']

        subpath_rules: list[str] = []
        seen: set[str] = set()
        for resolved in expand_pattern(pattern, self.working_dir):
            resolved_str = str(resolved)
            if resolved_str in seen:
                continue
            seen.add(resolved_str)
            if self._is_safe_path(resolved):
                subpath_rules.append(f'(allow file-write* (subpath "{resolved}"))')
        return subpath_rules, []

    def _build_exec_rules(self, pattern: str) -> list[str]:
        """Build process-exec rules for a pattern."""
        if pattern.startswith("/dev/"):
            return []

        rules = []
        seen: set[str] = set()
        for resolved in expand_pattern(pattern, self.working_dir):
            resolved_str = str(resolved)
            if resolved_str in seen:
                continue
            seen.add(resolved_str)
            if not self._is_safe_path(resolved):
                continue
            match_type = "subpath" if resolved.is_dir() else "literal"
            rules.append(f'(allow process-exec ({match_type} "{resolved}"))')
        return rules

    def _build_deny_rules(self) -> list[str]:
        """Build deny rules for hidden paths."""
        rules: list[str] = []
        deny_ops = ("file-read*", "file-write*")

        for pattern in self.config.filesystem.hidden:
            regex = pattern_to_regex(pattern, posix=True)
            if regex:
                for op in deny_ops:
                    rules.append(f'(deny {op} (regex #"{regex}"))')
            else:
                for expanded in expand_pattern(
                    pattern, self.working_dir, include_nonexistent=True
                ):
                    match_type = (
                        "subpath"
                        if expanded.is_dir() or not expanded.exists()
                        else "literal"
                    )
                    for op in deny_ops:
                        rules.append(f'(deny {op} ({match_type} "{expanded}"))')
        return rules

    def _build_working_dir_deny_rules(self) -> list[str]:
        """Build deny rules for working directory when '.' is not allowed."""
        rules: list[str] = []
        allow_working_read = "." in self.config.filesystem.read
        allow_working_write = "." in self.config.filesystem.write
        if not allow_working_read:
            rules.append(f'(deny file-read-data (subpath "{self.working_dir}"))')
            rules.append(f'(allow file-read-metadata (subpath "{self.working_dir}"))')
        if not allow_working_write:
            rules.append(f'(deny file-write* (subpath "{self.working_dir}"))')
        return rules

    def _build_profile(self) -> str:
        """Build seatbelt profile (.sb) content."""
        lines = [
            "(version 1)",
            "(deny default)",
            f'(import "{SEATBELT_BSD_PROFILE}")',
            "(allow process-fork)",
            "(allow process-info-pidinfo)",
            "(allow process-info-setcontrol)",
            "(allow signal (target self))",
            "(allow sysctl-read)",
            "(allow ipc-posix-shm)",
            "(allow ipc-posix-sem)",
            "(allow iokit-open)",
        ]

        for service in SEATBELT_MACH_SERVICES:
            lines.append(f'(allow mach-lookup (global-name "{service}"))')

        # Allow interpreter execution
        interpreter_paths = {Path(sys.executable), Path(sys.executable).resolve()}
        interpreter_dirs = {path.parent for path in interpreter_paths}
        for path in interpreter_paths:
            lines.append(f'(allow process-exec (literal "{path}"))')
            lines.append(f'(allow file-read* (literal "{path}"))')
        for directory in interpreter_dirs:
            lines.append(f'(allow process-exec (subpath "{directory}"))')
            lines.append(f'(allow file-read* (subpath "{directory}"))')

        lines.extend(self._build_working_dir_deny_rules())

        for pattern in self.config.filesystem.read:
            lines.extend(self._build_exec_rules(pattern))
            lines.extend(self._build_read_rules(pattern))

        for pattern in self.config.filesystem.write:
            lines.extend(self._build_exec_rules(pattern))
            subpath_rules, literal_rules = self._build_write_rules(pattern)
            lines.extend(subpath_rules)
            lines.extend(literal_rules)

        # Network rules
        if self._allows_network():
            lines.append(
                f'(allow network-outbound (path "{SEATBELT_MDNS_RESPONDER_PATH}"))'
            )
            if "*" in self.config.network.remote:
                lines.append("(allow network-outbound (remote tcp))")
                lines.append("(allow network-outbound (remote udp))")
                lines.append('(allow network-bind (local ip "*:*"))')
                lines.append("(allow network-inbound (local udp))")
            for socket in self.config.network.local:
                for expanded in expand_pattern(socket, self.working_dir):
                    lines.append(f'(allow network* (literal "{expanded}"))')

        lines.extend(self._build_deny_rules())
        return "\n".join(lines)

    def _get_profile_path(self) -> Path:
        """Get or create cached profile path."""
        if self._profile_path and self._profile_path.exists():
            return self._profile_path

        config_dict = self.config.model_dump(mode="json")

        if self.cache:
            cache_path = self.cache.get_path(
                self.config.name, self.working_dir, config_dict
            )
            if cache_path.exists():
                self._profile_path = cache_path
                return self._profile_path

            content = self._build_profile()
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w", dir=cache_path.parent, suffix=".sb", delete=False
            ) as f:
                f.write(content)
                temp_path = Path(f.name)
            os.replace(temp_path, cache_path)
            self._profile_path = cache_path
            return self._profile_path

        content = self._build_profile()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sb", delete=False) as f:
            f.write(content)
            self._profile_path = Path(f.name)
            return self._profile_path
