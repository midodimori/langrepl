"""Linux bubblewrap (bwrap) backend."""

from __future__ import annotations

import os
import shlex
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from langrepl.core.constants import PLATFORM
from langrepl.core.logging import get_logger
from langrepl.sandboxes.backends.base import SandboxBackend
from langrepl.sandboxes.constants import (
    BWRAP_AF_UNIX,
    BWRAP_BLOCKED_SYSCALLS,
    BWRAP_PTRACE_TRACEME,
)
from langrepl.utils.path import expand_pattern

if TYPE_CHECKING:
    from langrepl.configs.sandbox import SandboxConfig

logger = get_logger(__name__)

SECCOMP_AVAILABLE = False
seccomp: Any = None

if PLATFORM == "Linux":
    try:
        import seccomp  # type: ignore[import-not-found,no-redef]

        SECCOMP_AVAILABLE = True
    except ImportError:
        logger.warning("pyseccomp not installed, Unix socket blocking unavailable")


class BubblewrapBackend(SandboxBackend):
    """Linux bubblewrap implementation."""

    def __init__(
        self, config: SandboxConfig, working_dir: Path, cache_dir: Path | None = None
    ):
        super().__init__(config, working_dir, cache_dir)
        self._filter_path: Path | None = None

    def validate_environment(self) -> None:
        if PLATFORM != "Linux":
            raise RuntimeError(
                f"Bubblewrap sandbox requires Linux, current platform: {PLATFORM}"
            )
        if not shutil.which("bwrap"):
            raise RuntimeError("bwrap not found in PATH")

    def build_command(
        self, command: list[str], extra_env: dict[str, str] | None = None
    ) -> list[str]:
        """Build complete bwrap command."""
        args = ["bwrap", "--clearenv"]
        args.extend(self._build_env_args(extra_env))
        args.extend(["--tmpfs", "/", "--tmpfs", "/dev"])
        args.extend(self._build_read_args())
        args.extend(self._build_write_args())
        args.extend(self._build_hidden_args())
        args.extend(self._build_namespace_args())
        base_cmd = args + command

        filter_path = self._get_filter_path()
        if not filter_path:
            return base_cmd

        return [
            "bash",
            "-c",
            f'exec 3<{shlex.quote(str(filter_path))} && bwrap "$@"',
            "--",
            "--seccomp",
            "3",
        ] + base_cmd[1:]

    def _build_env_args(self, extra_env: dict[str, str] | None = None) -> list[str]:
        """Build environment variable arguments."""
        args: list[str] = []
        for key, value in self.get_sandbox_env().items():
            args.extend(["--setenv", key, value])
        if extra_env:
            for key, value in extra_env.items():
                args.extend(["--setenv", key, value])
        return args

    def _build_read_args(self) -> list[str]:
        """Build read-only mount arguments."""
        args: list[str] = []
        for pattern in self.config.filesystem.read:
            if pattern == ".":
                args.extend(["--ro-bind", str(self.working_dir), str(self.working_dir)])
                continue
            resolved_paths = expand_pattern(pattern, self.working_dir)
            if not resolved_paths and "*" in pattern:
                logger.warning(f"Sandbox read pattern '{pattern}' matched no files")
            for resolved in resolved_paths:
                if self._is_safe_path(resolved):
                    args.extend(["--ro-bind", str(resolved), str(resolved)])
        return args

    def _build_write_args(self) -> list[str]:
        """Build writable mount arguments."""
        args: list[str] = []
        for pattern in self.config.filesystem.write:
            if pattern == ".":
                args.extend(["--bind", str(self.working_dir), str(self.working_dir)])
                continue
            resolved_paths = expand_pattern(pattern, self.working_dir)
            if not resolved_paths and "*" in pattern:
                logger.warning(f"Sandbox write pattern '{pattern}' matched no files")
            for resolved in resolved_paths:
                if self._is_safe_path(resolved):
                    args.extend(["--bind", str(resolved), str(resolved)])
        return args

    def _build_hidden_args(self) -> list[str]:
        """Build mount arguments for hidden paths."""
        args: list[str] = []
        for pattern in self.config.filesystem.hidden:
            for path in expand_pattern(
                pattern, self.working_dir, include_nonexistent=False
            ):
                if path.is_file():
                    args.extend(["--ro-bind", "/dev/null", str(path)])
                elif path.is_dir():
                    args.extend(["--tmpfs", str(path)])
        return args

    def _build_namespace_args(self) -> list[str]:
        """Build namespace isolation arguments."""
        args = ["--unshare-user", "--uid", str(os.getuid()), "--gid", str(os.getgid())]
        args.extend(["--unshare-pid", "--unshare-ipc", "--unshare-uts"])
        args.extend(["--die-with-parent", "--new-session", "--proc", "/proc"])
        chdir_path = self.working_dir if self.includes_working_dir else Path("/")
        args.extend(["--chdir", str(chdir_path)])
        if self._allows_network():
            args.append("--share-net")
        else:
            args.append("--unshare-net")
        return args

    def _build_seccomp_filter(self) -> bytes | None:
        """Build seccomp BPF filter to block dangerous syscalls."""
        if not SECCOMP_AVAILABLE:
            return None
        try:
            f = seccomp.SyscallFilter(defaction=seccomp.ALLOW)
            f.add_rule(
                seccomp.ERRNO(1),
                "ptrace",
                seccomp.Arg(0, seccomp.EQ, BWRAP_PTRACE_TRACEME),
            )
            # Block AF_UNIX sockets unless local sockets configured
            if not self.config.network.local:
                f.add_rule(
                    seccomp.ERRNO(1),
                    "socket",
                    seccomp.Arg(0, seccomp.EQ, BWRAP_AF_UNIX),
                )
            for syscall in BWRAP_BLOCKED_SYSCALLS:
                try:
                    f.add_rule(seccomp.ERRNO(1), syscall)
                except Exception:
                    pass
            return f.export_bpf()
        except Exception as e:
            logger.warning(f"Failed to generate seccomp filter: {e}")
            return None

    def _get_filter_path(self) -> Path | None:
        """Get or create cached seccomp filter path."""
        if self._filter_path and self._filter_path.exists():
            return self._filter_path

        filter_path: Path | None = None
        if self.cache:
            config_dict = self.config.model_dump(mode="json")
            filter_path = self.cache.get_path(
                self.config.name, self.working_dir, config_dict, suffix=".bpf"
            )
            if filter_path.exists():
                self._filter_path = filter_path
                return self._filter_path

        bpf_data = self._build_seccomp_filter()
        if not bpf_data:
            return None

        if self.cache and filter_path:
            filter_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                dir=filter_path.parent, suffix=".bpf", delete=False
            ) as f:
                f.write(bpf_data)
                temp_path = Path(f.name)
            os.replace(temp_path, filter_path)
            self._filter_path = filter_path
        else:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".bpf") as f:
                f.write(bpf_data)
                self._filter_path = Path(f.name)

        return self._filter_path
