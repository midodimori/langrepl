"""Integration tests for sandbox execution.

These tests actually execute code in sandboxes and verify isolation.
Platform-specific tests are skipped when the sandbox backend is unavailable.

Note: These tests use simple stdlib modules instead of langrepl tools to avoid
dependencies on tool signatures and runtime injection which add complexity.
"""

import platform
import shutil

import pytest

from src.core.config import SandboxConfig, SandboxPermission, SandboxType
from src.sandboxes.impl.bubblewrap import BubblewrapSandbox
from src.sandboxes.impl.seatbelt import SeatbeltSandbox

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
            read_paths=[
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
        )
        return SeatbeltSandbox(config, temp_dir)

    @pytest.mark.asyncio
    async def test_execute_stdlib_function(self, sandbox):
        """Execute a stdlib function through sandbox."""
        result = await sandbox.execute(
            module_path="os.path",
            tool_name="basename",
            args={"p": "/home/user/file.txt"},
            timeout=15.0,
        )

        assert result["success"] is True
        assert result["content"] == "file.txt"

    @pytest.mark.asyncio
    async def test_execute_returns_dict(self, sandbox):
        """Execute function returning dict preserves structure."""
        result = await sandbox.execute(
            module_path="os",
            tool_name="getcwd",
            args={},
            timeout=15.0,
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
        )
        return BubblewrapSandbox(config, temp_dir)

    @pytest.mark.asyncio
    async def test_execute_stdlib_function(self, sandbox):
        """Execute a stdlib function through sandbox."""
        result = await sandbox.execute(
            module_path="os.path",
            tool_name="basename",
            args={"p": "/home/user/file.txt"},
            timeout=15.0,
        )

        assert result["success"] is True
        assert result["content"] == "file.txt"

    @pytest.mark.asyncio
    async def test_pid_namespace_isolation(self, sandbox):
        """Sandbox runs in isolated PID namespace."""
        result = await sandbox.execute(
            module_path="os",
            tool_name="getpid",
            args={},
            timeout=15.0,
        )

        assert result["success"] is True
        # In isolated namespace, PID should be low (often 1 or 2)
        pid = int(result["content"])
        assert pid < 100


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
                read_paths=[
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
            )
            return SeatbeltSandbox(config, temp_dir)
        elif IS_LINUX and HAS_BWRAP:
            config = SandboxConfig(
                name="test",
                type=SandboxType.BUBBLEWRAP,
                permissions=[SandboxPermission.NETWORK, SandboxPermission.FILESYSTEM],
            )
            return BubblewrapSandbox(config, temp_dir)
        else:
            pytest.skip("No sandbox available on this platform")

    @pytest.mark.asyncio
    async def test_execute_stdlib_function(self, sandbox):
        """Execute a stdlib function through sandbox."""
        result = await sandbox.execute(
            module_path="os.path",
            tool_name="basename",
            args={"p": "/home/user/file.txt"},
            timeout=15.0,
        )

        assert result["success"] is True
        assert result["content"] == "file.txt"

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
            module_path="os.path",
            tool_name="nonexistent_function",
            args={},
            timeout=15.0,
        )

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_function_exception_returns_error(self, sandbox):
        """Exception during function execution returns error."""
        # os.path.getsize on non-existent file raises FileNotFoundError
        result = await sandbox.execute(
            module_path="os.path",
            tool_name="getsize",
            args={"filename": "/nonexistent/path/to/file.txt"},
            timeout=15.0,
        )

        assert result["success"] is False
        assert "error" in result
