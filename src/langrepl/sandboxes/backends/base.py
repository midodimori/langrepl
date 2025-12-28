"""Base class for sandbox backends."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict

from langrepl.core.logging import get_logger
from langrepl.sandboxes.cache import ProfileCache
from langrepl.sandboxes.constants import (
    MAX_STDERR,
    MAX_STDOUT,
    SANDBOX_ENV_BASE,
    WORKER_MODULE,
)
from langrepl.utils.path import (
    expand_pattern,
    is_path_within,
    is_symlink_escape,
    matches_hidden,
)

if TYPE_CHECKING:
    from langrepl.configs.sandbox import SandboxConfig, SandboxType

logger = get_logger(__name__)


class SandboxBinding(BaseModel):
    """Binds patterns to a sandbox backend."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    patterns: list[str]
    backend: SandboxBackend | None


class SandboxBackend(ABC):
    """Abstract base for OS-specific sandbox implementations."""

    def __init__(
        self, config: SandboxConfig, working_dir: Path, cache_dir: Path | None = None
    ):
        self.config = config
        self.working_dir = self._resolve_working_dir(working_dir)
        self.cache = ProfileCache(cache_dir) if cache_dir else None

    @staticmethod
    def _resolve_working_dir(working_dir: Path) -> Path:
        """Resolve working directory, following symlinks to get real path."""
        resolved = working_dir.resolve()
        if not resolved.exists():
            raise ValueError(f"Working directory does not exist: {working_dir}")
        if not resolved.is_dir():
            raise ValueError(f"Working directory is not a directory: {working_dir}")
        return resolved

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def type(self) -> SandboxType:
        return self.config.type

    @property
    def includes_working_dir(self) -> bool:
        """Check if working directory is included in read or write paths."""
        return "." in self.config.filesystem.read or "." in self.config.filesystem.write

    def _allows_network(self) -> bool:
        """Check if network access is allowed (remote or local sockets)."""
        return "*" in self.config.network.remote or bool(self.config.network.local)

    def _get_allowed_boundaries(self) -> list[Path]:
        """Get all allowed path boundaries for symlink checking."""
        boundaries = []
        for pattern in self.config.filesystem.read + self.config.filesystem.write:
            if pattern == ".":
                continue
            for expanded in expand_pattern(pattern, self.working_dir):
                if expanded.is_absolute() and not expanded.is_symlink():
                    boundaries.append(expanded)
        return boundaries

    def _is_safe_path(self, path: Path) -> bool:
        """Check if path is safe (not a symlink escape and not hidden)."""
        if matches_hidden(path, self.config.filesystem.hidden, self.working_dir):
            return False
        boundaries = self._get_allowed_boundaries()
        if self.includes_working_dir:
            boundaries.append(self.working_dir)
        if is_symlink_escape(path, boundaries):
            return False
        return True

    @staticmethod
    async def _collect_output(
        stream: asyncio.StreamReader | None, max_size: int
    ) -> tuple[bytes, bool]:
        """Collect output with size limit, returns (data, truncated)."""
        if not stream:
            return b"", False
        chunks, size, truncated = [], 0, False
        while chunk := await stream.read(65536):
            if size < max_size:
                chunks.append(chunk)
                size += len(chunk)
            else:
                truncated = True
        return b"".join(chunks), truncated

    def get_sandbox_env(self) -> dict[str, str]:
        """Get environment variables for sandbox with user tool paths."""
        home = os.environ.get("HOME", str(Path.home()))
        user_paths = f"{home}/.local/bin"
        base_path = SANDBOX_ENV_BASE.get("PATH", "")
        return {
            "HOME": home,
            **SANDBOX_ENV_BASE,
            "PATH": f"{user_paths}:{base_path}",
        }

    @abstractmethod
    def build_command(
        self, command: list[str], extra_env: dict[str, str] | None = None
    ) -> list[str]:
        """Build complete sandboxed command."""

    @abstractmethod
    def validate_environment(self) -> None:
        """Validate that the sandbox backend is available."""

    def _is_path_in_config(self, path: Path) -> bool:
        """Check if a path is covered by configured read/write paths."""
        for pattern in self.config.filesystem.read + self.config.filesystem.write:
            if pattern == ".":
                if is_path_within(path, [self.working_dir]):
                    return True
                continue
            for expanded in expand_pattern(pattern, self.working_dir):
                if is_path_within(path, [expanded]):
                    return True
        return False

    def warn_symlink_issues(self) -> None:
        """Warn about symlinks in configured paths."""
        for pattern in self.config.filesystem.read + self.config.filesystem.write:
            if pattern == ".":
                continue
            for expanded in expand_pattern(pattern, self.working_dir):
                if not expanded.is_symlink():
                    continue
                try:
                    target = expanded.resolve()
                    if not self._is_path_in_config(target):
                        logger.warning(
                            f"[{self.config.name}] {expanded} -> {target}\n"
                            f"  Add '{target}' or '{target.parent}' to filesystem.read\n"
                            f"  Discover symlink targets with: readlink -f {expanded}"
                        )
                except OSError:
                    pass

    async def execute(
        self,
        module_path: str,
        tool_name: str,
        args: dict[str, Any],
        timeout: float = 60.0,
        tool_runtime: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a tool in the sandbox via worker module."""
        try:
            request = json.dumps(
                {
                    "module": module_path,
                    "tool_name": tool_name,
                    "args": args,
                    "tool_runtime": tool_runtime,
                },
                default=str,
            )
        except (TypeError, ValueError) as e:
            return {"success": False, "error": f"Cannot serialize tool args: {e}"}

        sandbox_cmd = self.build_command([sys.executable, "-m", WORKER_MODULE])
        logger.debug(f"Executing in {self.name} [{self.type}]: {' '.join(sandbox_cmd)}")
        cwd = (
            str(self.working_dir)
            if self.includes_working_dir
            else str(Path(sys.executable).parent)
        )

        try:
            process = await asyncio.create_subprocess_exec(
                *sandbox_cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                start_new_session=True,
            )

            if process.stdin:
                process.stdin.write(request.encode())
                await process.stdin.drain()
                process.stdin.close()

            stdout_task = asyncio.create_task(
                self._collect_output(process.stdout, MAX_STDOUT)
            )
            stderr_task = asyncio.create_task(
                self._collect_output(process.stderr, MAX_STDERR)
            )

            try:
                (stdout, stdout_truncated), (stderr, _) = await asyncio.wait_for(
                    asyncio.gather(stdout_task, stderr_task),
                    timeout=timeout,
                )
                await process.wait()
            except TimeoutError:
                try:
                    if process.pid:
                        os.killpg(process.pid, signal.SIGKILL)
                except (ProcessLookupError, OSError):
                    pass
                process.kill()
                await process.wait()
                for task in (stdout_task, stderr_task):
                    if not task.done():
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                return {
                    "success": False,
                    "error": f"Sandbox execution timed out after {timeout}s",
                }

            if stdout_truncated:
                return {
                    "success": False,
                    "error": f"Output exceeded {MAX_STDOUT // (1024 * 1024)}MB limit",
                }

            if process.returncode != 0:
                return {
                    "success": False,
                    "error": f"{self.name} failed with code {process.returncode}",
                    "stderr": stderr.decode("utf-8", errors="replace"),
                }

            try:
                return json.loads(stdout.decode("utf-8"))
            except json.JSONDecodeError:
                return {
                    "success": False,
                    "error": "Failed to parse worker output",
                    "stdout": stdout.decode("utf-8", errors="replace"),
                }

        except Exception as e:
            return {"success": False, "error": str(e)}
