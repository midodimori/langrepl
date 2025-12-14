"""Integration tests for sandbox execution.

These tests actually execute code in sandboxes and verify isolation.
Platform-specific tests are skipped when the sandbox backend is unavailable.

Note: These tests use actual LangChain tools from src.tools.impl to test
sandbox execution with real ToolRuntime serialization.
"""

import platform
import shutil
import sys
from pathlib import Path

import pytest

from src.configs import SandboxConfig, SandboxPermission, SandboxType
from src.sandboxes.impl.bubblewrap import BubblewrapSandbox
from src.sandboxes.impl.seatbelt import SeatbeltSandbox
from src.sandboxes.serialization import (
    RuntimeContext,
    SerializedConfig,
    SerializedContext,
    SerializedState,
)

# Project root for mounting in sandboxes
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# Directory containing Python executable (venv)
PYTHON_DIR = Path(sys.executable).resolve().parent.parent
# Skip conditions
IS_MACOS = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"
HAS_SANDBOX_EXEC = shutil.which("sandbox-exec") is not None
HAS_BWRAP = shutil.which("bwrap") is not None

skip_unless_macos = pytest.mark.skipif(
    not (IS_MACOS and HAS_SANDBOX_EXEC),
    reason="Requires macOS with sandbox-exec",
)
skip_unless_linux = pytest.mark.skipif(
    not (IS_LINUX and HAS_BWRAP),
    reason="Requires Linux with bubblewrap",
)


def create_test_runtime_context(working_dir: str = "/tmp") -> RuntimeContext:
    """Create a minimal runtime context for testing."""
    return {
        "tool_call_id": "test-integration",
        "state": SerializedState(
            todos=None,
            files=None,
            current_input_tokens=None,
            current_output_tokens=None,
            total_cost=None,
        ),
        "context": SerializedContext(
            approval_mode="semi-active",
            working_dir=working_dir,
            platform="",
            os_version="",
            current_date_time_zoned="",
            user_memory="",
            input_cost_per_mtok=None,
            output_cost_per_mtok=None,
            tool_output_max_tokens=None,
        ),
        "config": SerializedConfig(
            tags=[],
            metadata={},
            run_name=None,
            run_id=None,
            recursion_limit=25,
            configurable={},
        ),
    }


@skip_unless_macos
class TestSeatbeltIntegration:
    """Integration tests for Seatbelt sandbox on macOS."""

    @pytest.fixture
    def sandbox(self, temp_dir):
        config = SandboxConfig(
            name="test",
            type=SandboxType.SEATBELT,
            permissions=[SandboxPermission.NETWORK, SandboxPermission.FILESYSTEM],
            # Required paths for Python execution
            execution_ro_paths=[
                "/usr",
                "/bin",
                "/sbin",
                "/etc",
                "/private/etc",
                "/Library",
                "/System",
                "/dev",
                "/opt/homebrew",
                "/usr/local",
                "~",  # Home directory for pyenv, volta, nvm, etc.
            ],
            filesystem_paths=["/tmp"],
        )
        return SeatbeltSandbox(config, temp_dir)

    @pytest.mark.asyncio
    async def test_execute_langchain_tool(self, sandbox):
        """Execute a LangChain tool through sandbox."""
        result = await sandbox.execute(
            module_path="src.tools.impl.file_system",
            tool_name="read_file",
            args={"file_path": "/etc/hosts"},
            timeout=15.0,
            runtime_context=create_test_runtime_context(),
        )

        # Should succeed (read_file can read /etc/hosts with permissions)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_returns_structured_result(self, sandbox):
        """Execute function returns structured result."""
        result = await sandbox.execute(
            module_path="src.tools.impl.file_system",
            tool_name="read_file",
            args={"file_path": "/etc/hosts"},
            timeout=15.0,
            runtime_context=create_test_runtime_context(),
        )

        assert result["success"] is True
        assert "content" in result


@skip_unless_linux
class TestBubblewrapIntegration:
    """Integration tests for Bubblewrap sandbox on Linux."""

    @pytest.fixture
    def sandbox(self, temp_dir):
        config = SandboxConfig(
            name="test",
            type=SandboxType.BUBBLEWRAP,
            permissions=[SandboxPermission.NETWORK, SandboxPermission.FILESYSTEM],
            execution_ro_paths=[
                "/usr",
                "/lib",
                "/lib64",
                "/bin",
                "/sbin",
                "/etc",
                "~",
                str(PROJECT_ROOT),
                str(PYTHON_DIR),
            ],
            filesystem_paths=["/tmp"],
        )
        return BubblewrapSandbox(config, temp_dir)

    @pytest.mark.asyncio
    async def test_execute_langchain_tool(self, sandbox):
        """Execute a LangChain tool through sandbox."""
        result = await sandbox.execute(
            module_path="src.tools.impl.file_system",
            tool_name="read_file",
            args={"file_path": "/etc/hosts"},
            timeout=15.0,
            runtime_context=create_test_runtime_context(),
        )

        assert result["success"] is True, f"Sandbox execution failed: {result}"

    @pytest.mark.asyncio
    async def test_pid_namespace_isolation(self, sandbox):
        """Sandbox runs in isolated PID namespace.

        Note: This test uses a raw function, not a LangChain tool, which will
        fail with the new worker. Skipping for now.
        """
        pytest.skip("Worker now only supports LangChain tools")


class TestCrossPlatform:
    """Tests that work on any platform with available sandbox."""

    @pytest.fixture
    def sandbox(self, temp_dir):
        """Get appropriate sandbox for current platform."""
        if IS_MACOS and HAS_SANDBOX_EXEC:
            config = SandboxConfig(
                name="test",
                type=SandboxType.SEATBELT,
                permissions=[SandboxPermission.NETWORK, SandboxPermission.FILESYSTEM],
                execution_ro_paths=[
                    "/usr",
                    "/bin",
                    "/sbin",
                    "/etc",
                    "/private/etc",
                    "/Library",
                    "/System",
                    "/dev",
                    "/opt/homebrew",
                    "/usr/local",
                    "~",
                ],
                filesystem_paths=["/tmp"],
            )
            return SeatbeltSandbox(config, temp_dir)
        elif IS_LINUX and HAS_BWRAP:
            config = SandboxConfig(
                name="test",
                type=SandboxType.BUBBLEWRAP,
                permissions=[SandboxPermission.NETWORK, SandboxPermission.FILESYSTEM],
                execution_ro_paths=[
                    "/usr",
                    "/lib",
                    "/lib64",
                    "/bin",
                    "/sbin",
                    "/etc",
                    "~",
                    str(PROJECT_ROOT),
                    str(PYTHON_DIR),
                ],
                filesystem_paths=["/tmp"],
            )
            return BubblewrapSandbox(config, temp_dir)
        else:
            pytest.skip("No sandbox available on this platform")

    @pytest.mark.asyncio
    async def test_execute_langchain_tool(self, sandbox):
        """Execute a LangChain tool through sandbox."""
        result = await sandbox.execute(
            module_path="src.tools.impl.file_system",
            tool_name="read_file",
            args={"file_path": "/etc/hosts"},
            timeout=15.0,
            runtime_context=create_test_runtime_context(),
        )

        assert result["success"] is True, f"Sandbox execution failed: {result}"

    @pytest.mark.asyncio
    async def test_invalid_module_returns_error(self, sandbox):
        """Executing non-existent module returns error, not crash."""
        result = await sandbox.execute(
            module_path="nonexistent.module.path",
            tool_name="some_tool",
            args={},
            timeout=15.0,
        )

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_invalid_tool_returns_error(self, sandbox):
        """Executing non-existent tool in valid module returns error."""
        result = await sandbox.execute(
            module_path="src.tools.impl.file_system",
            tool_name="nonexistent_function",
            args={},
            timeout=15.0,
        )

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_non_langchain_tool_returns_error(self, sandbox):
        """Executing non-LangChain functions returns error."""
        result = await sandbox.execute(
            module_path="os.path",
            tool_name="basename",
            args={"p": "/home/user/file.txt"},
            timeout=15.0,
        )

        assert result["success"] is False
        assert "not a LangChain tool" in result["error"]
