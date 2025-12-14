"""Tests for Seatbelt sandbox - security edge cases."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.configs import SandboxConfig, SandboxPermission, SandboxType
from src.sandboxes.impl.seatbelt import (
    SeatbeltSandbox,
    generate_seatbelt_profile,
)


class TestPermissionBoundaries:
    """Tests for permission boundary enforcement."""

    def test_no_network_without_permission(self):
        """Network rules absent when NETWORK permission not granted."""
        config = SandboxConfig(
            name="test",
            type=SandboxType.SEATBELT,
            permissions=[SandboxPermission.FILESYSTEM],
        )
        profile = generate_seatbelt_profile(config)

        assert "network-outbound" not in profile
        assert "network-inbound" not in profile
        assert "system-socket" not in profile

    def test_no_working_dir_write_without_filesystem_permission(self):
        """Working dir not writable when FILESYSTEM permission not granted."""
        config = SandboxConfig(
            name="test",
            type=SandboxType.SEATBELT,
            permissions=[SandboxPermission.NETWORK],
        )
        working_dir = Path("/home/user/project")
        profile = generate_seatbelt_profile(config, working_dir=working_dir)

        assert f'(allow file-write* (subpath "{working_dir}"))' not in profile

    def test_empty_permissions_minimal_profile(self):
        """Empty permissions list results in minimal access profile."""
        config = SandboxConfig(
            name="test",
            type=SandboxType.SEATBELT,
            permissions=[],
        )
        profile = generate_seatbelt_profile(config, working_dir=Path("/project"))

        # No network
        assert "network-outbound" not in profile
        # No working dir write (only temp paths writable)
        assert '(allow file-write* (subpath "/project"))' not in profile


class TestSeatbeltSandboxExecution:
    """Tests for sandbox execution edge cases."""

    @pytest.fixture
    def sandbox(self, temp_dir):
        config = SandboxConfig(
            name="test",
            type=SandboxType.SEATBELT,
            permissions=[SandboxPermission.FILESYSTEM],
        )
        return SeatbeltSandbox(config, temp_dir)

    def _create_mock_process(
        self, stdout_data: bytes, stderr_lines: list[bytes], returncode: int
    ):
        """Create a mock process with proper stream mocks."""
        from unittest.mock import AsyncMock, MagicMock

        mock_process = MagicMock()
        mock_process.returncode = returncode

        # Mock stdin
        mock_process.stdin = MagicMock()
        mock_process.stdin.write = MagicMock()
        mock_process.stdin.drain = AsyncMock()
        mock_process.stdin.close = MagicMock()

        # Mock stdout.read(chunk_size) - returns data then empty
        stdout_iter = iter([stdout_data, b""])
        mock_process.stdout = MagicMock()
        mock_process.stdout.read = AsyncMock(side_effect=lambda _: next(stdout_iter))

        # Mock stderr.read(chunk_size) - returns data then empty
        stderr_data = b"".join(stderr_lines)
        stderr_iter = iter([stderr_data, b""])
        mock_process.stderr = MagicMock()
        mock_process.stderr.read = AsyncMock(side_effect=lambda _: next(stderr_iter))

        # Mock wait()
        mock_process.wait = AsyncMock()

        return mock_process

    @pytest.mark.asyncio
    async def test_execute_returns_structured_error_on_violation(self, sandbox):
        """Sandbox violations return structured error, not crash."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = self._create_mock_process(
                stdout_data=b"",
                stderr_lines=[b"deny(1) file-write-create /etc/passwd\n"],
                returncode=1,
            )

            result = await sandbox.execute("test.module", "tool", {}, timeout=15.0)

        assert result["success"] is False
        assert "failed with code 1" in result["error"]
        assert "deny" in result["stderr"]

    @pytest.mark.asyncio
    async def test_execute_handles_non_utf8_output(self, sandbox):
        """Non-UTF8 output is handled gracefully."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = self._create_mock_process(
                stdout_data=b"\xff\xfe",
                stderr_lines=[],
                returncode=0,
            )

            result = await sandbox.execute("test.module", "tool", {}, timeout=15.0)

        # Should not crash, should return error
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_execute_handles_empty_output(self, sandbox):
        """Empty output returns parse error, not crash."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = self._create_mock_process(
                stdout_data=b"",
                stderr_lines=[],
                returncode=0,
            )

            result = await sandbox.execute("test.module", "tool", {}, timeout=15.0)

        assert result["success"] is False
        assert "parse" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_execute_large_output_not_truncated(self, sandbox):
        """Large output is passed through (no artificial truncation)."""
        large_content = "x" * 100000
        expected_output = json.dumps({"success": True, "content": large_content})

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = self._create_mock_process(
                stdout_data=expected_output.encode(),
                stderr_lines=[],
                returncode=0,
            )

            result = await sandbox.execute("test.module", "tool", {}, timeout=15.0)

        assert result["success"] is True
        assert len(result["content"]) == 100000


class TestWrapMcpCommand:
    """Tests for MCP command wrapping."""

    @patch(
        "src.sandboxes.impl.seatbelt._write_temp_profile",
        return_value="/tmp/test.sb",
    )
    def test_command_with_spaces_in_args(self, mock_profile, temp_dir):
        """Arguments with spaces are preserved."""
        config = SandboxConfig(
            name="test",
            type=SandboxType.SEATBELT,
            permissions=[],
        )
        sandbox = SeatbeltSandbox(config, temp_dir)

        cmd, args = sandbox.wrap_mcp_command(
            "node", ["server.js", "--name", "my server name"]
        )

        assert cmd == "sandbox-exec"
        assert args == [
            "-f",
            "/tmp/test.sb",
            "node",
            "server.js",
            "--name",
            "my server name",
        ]

    @patch(
        "src.sandboxes.impl.seatbelt._write_temp_profile",
        return_value="/tmp/test.sb",
    )
    def test_command_with_special_chars(self, mock_profile, temp_dir):
        """Special characters in command/args are preserved."""
        config = SandboxConfig(
            name="test",
            type=SandboxType.SEATBELT,
            permissions=[],
        )
        sandbox = SeatbeltSandbox(config, temp_dir)

        cmd, args = sandbox.wrap_mcp_command(
            "/usr/bin/env", ["bash", "-c", "echo $HOME && ls -la"]
        )

        assert args == [
            "-f",
            "/tmp/test.sb",
            "/usr/bin/env",
            "bash",
            "-c",
            "echo $HOME && ls -la",
        ]

    def test_factory_raises_when_sandbox_exec_unavailable(self, temp_dir):
        """Factory raises RuntimeError when sandbox-exec is not available."""
        from src.sandboxes.factory import SandboxFactory

        config = SandboxConfig(
            name="test",
            type=SandboxType.SEATBELT,
            permissions=[],
        )

        with patch(
            "src.sandboxes.impl.seatbelt.SeatbeltSandbox.is_available",
            return_value=False,
        ):
            with pytest.raises(RuntimeError, match="Seatbelt sandbox is not available"):
                SandboxFactory.create(config, temp_dir)
