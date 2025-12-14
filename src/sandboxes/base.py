"""Sandbox execution base classes."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.configs import SandboxPermission
from src.core.logging import get_logger

if TYPE_CHECKING:
    from src.configs import SandboxConfig


logger = get_logger(__name__)

WORKER_MODULE = "src.sandboxes.worker"

# Project root: src/sandboxes/base.py -> 2 parents up
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Output size limits
MAX_STDOUT = 10 * 1024 * 1024  # 10MB
MAX_STDERR = 1024 * 1024  # 1MB


class Sandbox(ABC):
    """Abstract base class for sandbox."""

    # Subclasses should override this for error messages
    sandbox_name: str = "sandbox"

    @staticmethod
    async def _collect_output(
        stream: asyncio.StreamReader | None,
        max_size: int,
    ) -> tuple[bytes, bool]:
        """Collect output with size limit, returns (data, truncated)."""
        if stream is None:
            return b"", False
        chunks: list[bytes] = []
        size = 0
        truncated = False
        while True:
            chunk = await stream.read(65536)
            if not chunk:
                break
            if size < max_size:
                chunks.append(chunk)
                size += len(chunk)
            else:
                truncated = True
        return b"".join(chunks), truncated

    def __init__(self, config: SandboxConfig, working_dir: Path):
        self.config = config
        self.working_dir = working_dir

    @classmethod
    @abstractmethod
    def is_available(cls) -> bool:
        """Check if this sandbox backend is available on the system."""

    @abstractmethod
    def _build_sandbox_command(
        self,
        permissions: list[SandboxPermission],
    ) -> list[str]:
        """Build the sandbox command prefix (e.g., ['sandbox-exec', '-f', 'profile']).

        The worker module invocation will be appended automatically.
        """

    def _prepare_env(
        self,
        env: dict[str, str],
        permissions: list[SandboxPermission],
    ) -> None:
        """Hook for subclasses to modify environment. Called before process spawn."""

    def _compute_effective_permissions(
        self, tool_permissions: list[SandboxPermission] | None
    ) -> list[SandboxPermission]:
        """Compute effective permissions (intersection of sandbox and tool permissions)."""
        if tool_permissions is None:
            return list(self.config.permissions)
        return [p for p in tool_permissions if self.config.has_permission(p)]

    async def sandbox_mcp_command(
        self,
        name: str,
        command: str,
        args: list[str],
        mcp_permissions: list[SandboxPermission],
    ) -> tuple[str, list[str], bool]:
        """Sandbox MCP command: check permissions → apply injectors → wrap."""
        from src.sandboxes.injectors import INJECTORS

        # Block if MCP needs permissions sandbox doesn't grant
        missing = [p for p in mcp_permissions if not self.config.has_permission(p)]
        if missing:
            logger.warning(
                f"Blocking MCP '{name}': needs {[p.value for p in missing]}, "
                f"sandbox grants {[p.value for p in self.config.permissions]}"
            )
            return command, args, False

        # Apply injectors (network isolation, package caching, etc.)
        for injector in INJECTORS:
            if injector.should_apply(command, args, self.config):
                command, args, ok = await injector.apply(
                    name, command, args, self.config
                )
                if not ok:
                    return command, args, False
                break

        return *self.wrap_mcp_command(command, args, mcp_permissions), True

    async def execute(
        self,
        module_path: str,
        tool_name: str,
        args: dict[str, Any],
        timeout: float,
        tool_permissions: list[SandboxPermission] | None = None,
    ) -> dict[str, Any]:
        """Execute a tool in the sandbox.

        Args:
            tool_permissions: Tool's declared permissions. If provided, the sandbox
                profile will use the intersection of these and the sandbox config
                permissions (tool gets only what it needs, capped by sandbox policy).
        """
        try:
            request = json.dumps(
                {
                    "module": module_path,
                    "tool_name": tool_name,
                    "args": args,
                },
                default=str,  # Convert non-serializable objects to string
            )
        except (TypeError, ValueError) as e:
            return {
                "success": False,
                "error": f"Cannot serialize tool args for sandbox: {e}",
            }

        effective_perms = self._compute_effective_permissions(tool_permissions)
        sandbox_cmd = self._build_sandbox_command(effective_perms)
        sandbox_cmd.extend([sys.executable, "-m", WORKER_MODULE])

        logger.debug(f"Executing in {self.sandbox_name}: {' '.join(sandbox_cmd)}")

        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = str(PROJECT_ROOT)
            env["PYTHONUNBUFFERED"] = "1"
            if SandboxPermission.FILESYSTEM in effective_perms:
                env["LANGREPL_WORKING_DIR"] = str(self.working_dir)

            # Allow subclasses to modify env
            self._prepare_env(env, effective_perms)

            process = await asyncio.create_subprocess_exec(
                *sandbox_cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=PROJECT_ROOT,
                env=env,
                start_new_session=True,
            )

            # Write request to stdin
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
                stdout, stdout_truncated = await asyncio.wait_for(
                    stdout_task, timeout=timeout
                )
                await process.wait()
                try:
                    stderr, _ = await asyncio.wait_for(stderr_task, timeout=1.0)
                except (TimeoutError, asyncio.CancelledError):
                    stderr_task.cancel()
                    stderr = b""
            except TimeoutError:
                process.kill()
                await process.wait()
                stdout_task.cancel()
                stderr_task.cancel()
                stderr = stderr_task.result()[0] if stderr_task.done() else b""
                return {
                    "success": False,
                    "error": f"Sandbox execution timed out after {timeout} seconds",
                    "stderr": (
                        stderr.decode("utf-8", errors="replace") if stderr else ""
                    ),
                }
            except asyncio.CancelledError:
                process.kill()
                await process.wait()
                stdout_task.cancel()
                stderr_task.cancel()
                raise

            if stdout_truncated:
                return {
                    "success": False,
                    "error": f"Sandbox output exceeded {MAX_STDOUT // (1024 * 1024)}MB limit",
                    "stdout": stdout.decode("utf-8", errors="replace")[:10000],
                }

            if process.returncode != 0:
                return {
                    "success": False,
                    "error": f"{self.sandbox_name} failed with code {process.returncode}",
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

        except asyncio.CancelledError:
            raise
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    @abstractmethod
    def _build_mcp_wrapper(
        self,
        command: str,
        args: list[str],
        permissions: list[SandboxPermission],
    ) -> tuple[str, list[str]]:
        """Build the MCP wrapper command.

        Args:
            command: Original MCP server command
            args: Original MCP server args
            permissions: Effective permissions (already computed)

        Returns:
            Tuple of (wrapper_command, full_args_including_original_command)
        """

    def wrap_mcp_command(
        self,
        command: str,
        args: list[str],
        permissions: list[SandboxPermission] | None = None,
    ) -> tuple[str, list[str]]:
        """Wrap an MCP server command with sandbox restrictions.

        Args:
            permissions: MCP server's declared permissions. If provided, the sandbox
                profile will use the intersection of these and the sandbox config
                permissions.
        """
        effective_perms = self._compute_effective_permissions(permissions)
        logger.debug(
            f"{self.sandbox_name} for MCP '{command}' with perms: "
            f"{[p.value for p in effective_perms]}"
        )
        return self._build_mcp_wrapper(command, args, effective_perms)

    def cleanup(self) -> None:
        """Clean up any resources. Override in subclasses if needed."""
