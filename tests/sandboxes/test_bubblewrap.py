"""Tests for Bubblewrap sandbox - security edge cases."""

import json
from unittest.mock import patch

import pytest

from src.configs import SandboxConfig, SandboxPermission, SandboxType
from src.sandboxes.impl.bubblewrap import BubblewrapSandbox


class TestBwrapArgs:
    """Tests for bwrap argument generation."""

    def test_no_network_without_permission(self, temp_dir):
        """Network is unshared when NETWORK permission not granted."""
        config = SandboxConfig(
            name="test",
            type=SandboxType.BUBBLEWRAP,
            permissions=[SandboxPermission.FILESYSTEM],
        )
        sandbox = BubblewrapSandbox(config, temp_dir)
        args = sandbox._build_bwrap_args()

        assert "--unshare-net" in args

    def test_network_allowed_with_permission(self, temp_dir):
        """Network is NOT unshared when NETWORK permission granted."""
        config = SandboxConfig(
            name="test",
            type=SandboxType.BUBBLEWRAP,
            permissions=[SandboxPermission.NETWORK],
        )
        sandbox = BubblewrapSandbox(config, temp_dir)
        args = sandbox._build_bwrap_args()

        assert "--unshare-net" not in args

    def test_no_working_dir_bind_without_filesystem_permission(self, temp_dir):
        """Working dir not bound when FILESYSTEM permission not granted."""
        config = SandboxConfig(
            name="test",
            type=SandboxType.BUBBLEWRAP,
            permissions=[SandboxPermission.NETWORK],
        )
        sandbox = BubblewrapSandbox(config, temp_dir)
        args = sandbox._build_bwrap_args()

        # Should not have --bind for working_dir
        bind_indices = [i for i, arg in enumerate(args) if arg == "--bind"]
        for idx in bind_indices:
            assert str(temp_dir) not in args[idx + 1 : idx + 3]

    def test_working_dir_bound_with_filesystem_permission(self, temp_dir):
        """Working dir is bound when FILESYSTEM permission granted."""
        config = SandboxConfig(
            name="test",
            type=SandboxType.BUBBLEWRAP,
            permissions=[SandboxPermission.FILESYSTEM],
        )
        sandbox = BubblewrapSandbox(config, temp_dir)
        args = sandbox._build_bwrap_args()

        # Should have --bind for working_dir
        assert "--bind" in args
        bind_idx = args.index("--bind")
        assert args[bind_idx + 1] == str(temp_dir)

    def test_empty_permissions_minimal_args(self, temp_dir):
        """Empty permissions list results in minimal access."""
        config = SandboxConfig(
            name="test",
            type=SandboxType.BUBBLEWRAP,
            permissions=[],
        )
        sandbox = BubblewrapSandbox(config, temp_dir)
        args = sandbox._build_bwrap_args()

        # No network
        assert "--unshare-net" in args
        # No working dir bind for temp_dir
        bind_indices = [i for i, arg in enumerate(args) if arg == "--bind"]
        for idx in bind_indices:
            assert str(temp_dir) not in args[idx + 1 : idx + 3]


class TestBubblewrapSandboxExecution:
    """Tests for sandbox execution edge cases."""

    @pytest.fixture
    def sandbox(self, temp_dir):
        config = SandboxConfig(
            name="test",
            type=SandboxType.BUBBLEWRAP,
            permissions=[SandboxPermission.FILESYSTEM],
        )
        return BubblewrapSandbox(config, temp_dir)

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
        with (
            patch("shutil.which", return_value="/usr/bin/bwrap"),
            patch("asyncio.create_subprocess_exec") as mock_exec,
        ):
            mock_exec.return_value = self._create_mock_process(
                stdout_data=b"",
                stderr_lines=[b"bwrap: Can't open /etc/passwd for writing\n"],
                returncode=1,
            )

            result = await sandbox.execute("test.module", "tool", {}, timeout=15.0)

        assert result["success"] is False
        assert "failed with code 1" in result["error"]
        assert "Can't open" in result["stderr"]

    @pytest.mark.asyncio
    async def test_execute_handles_non_utf8_output(self, sandbox):
        """Non-UTF8 output is handled gracefully."""
        with (
            patch("shutil.which", return_value="/usr/bin/bwrap"),
            patch("asyncio.create_subprocess_exec") as mock_exec,
        ):
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
        with (
            patch("shutil.which", return_value="/usr/bin/bwrap"),
            patch("asyncio.create_subprocess_exec") as mock_exec,
        ):
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

        with (
            patch("shutil.which", return_value="/usr/bin/bwrap"),
            patch("asyncio.create_subprocess_exec") as mock_exec,
        ):
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

    @patch("shutil.which", return_value="/usr/bin/node")
    def test_command_with_spaces_in_args(self, mock_which, temp_dir):
        """Arguments with spaces are preserved."""
        config = SandboxConfig(
            name="test",
            type=SandboxType.BUBBLEWRAP,
            permissions=[],
        )
        sandbox = BubblewrapSandbox(config, temp_dir)

        cmd, args = sandbox.wrap_mcp_command(
            "node", ["server.js", "--name", "my server name"]
        )

        assert cmd == "bwrap"
        # Check command and args are at the end after --
        assert "--" in args
        dash_idx = args.index("--")
        assert args[dash_idx + 1] == "/usr/bin/node"
        assert args[dash_idx + 2 :] == ["server.js", "--name", "my server name"]

    @patch("shutil.which", return_value="/usr/bin/env")
    def test_command_with_special_chars(self, mock_which, temp_dir):
        """Special characters in command/args are preserved."""
        config = SandboxConfig(
            name="test",
            type=SandboxType.BUBBLEWRAP,
            permissions=[],
        )
        sandbox = BubblewrapSandbox(config, temp_dir)

        cmd, args = sandbox.wrap_mcp_command(
            "/usr/bin/env", ["bash", "-c", "echo $HOME && ls -la"]
        )

        assert cmd == "bwrap"
        dash_idx = args.index("--")
        assert args[dash_idx + 2 :] == ["bash", "-c", "echo $HOME && ls -la"]

    def test_factory_raises_when_bwrap_unavailable(self, temp_dir):
        """Factory raises RuntimeError when bwrap is not available."""
        from src.sandboxes.factory import SandboxFactory

        config = SandboxConfig(
            name="test",
            type=SandboxType.BUBBLEWRAP,
            permissions=[],
        )

        with patch(
            "src.sandboxes.impl.bubblewrap.BubblewrapSandbox.is_available",
            return_value=False,
        ):
            with pytest.raises(
                RuntimeError, match="Bubblewrap sandbox is not available"
            ):
                SandboxFactory.create(config, temp_dir)
