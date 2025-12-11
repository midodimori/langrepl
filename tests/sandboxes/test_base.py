"""Tests for sandbox base class - edge cases."""

from src.sandboxes.base import Sandbox


class TestInjectOfflineFlag:
    """Tests for _inject_offline_flag with shlex parsing."""

    def test_direct_npx_command(self):
        """Direct npx command gets --offline injected."""
        command, args = Sandbox._inject_offline_flag(
            "npx", ["@mcp/server", "--port", "3000"]
        )

        assert command == "npx"
        assert args == ["--offline", "@mcp/server", "--port", "3000"]

    def test_direct_uvx_command(self):
        """Direct uvx command gets --offline injected."""
        command, args = Sandbox._inject_offline_flag("uvx", ["ruff", "check", "."])

        assert command == "uvx"
        assert args == ["--offline", "ruff", "check", "."]

    def test_sh_c_npx_command(self):
        """sh -c 'npx ...' gets --offline injected via shlex."""
        command, args = Sandbox._inject_offline_flag(
            "sh", ["-c", "npx @mcp/server --port 3000"]
        )

        assert command == "sh"
        assert args[0] == "-c"
        assert "--offline" in args[1]
        # shlex.join should properly reconstruct
        assert "npx --offline" in args[1]

    def test_sh_c_uvx_command(self):
        """sh -c 'uvx ...' gets --offline injected via shlex."""
        command, args = Sandbox._inject_offline_flag("sh", ["-c", "uvx ruff check ."])

        assert command == "sh"
        assert "--offline" in args[1]

    def test_already_has_offline_flag(self):
        """Commands already having --offline are not modified."""
        command, args = Sandbox._inject_offline_flag(
            "npx", ["--offline", "@mcp/server"]
        )

        assert args == ["--offline", "@mcp/server"]
        # Should not have double --offline
        assert args.count("--offline") == 1

    def test_sh_c_already_has_offline(self):
        """sh -c with existing --offline is not modified."""
        command, args = Sandbox._inject_offline_flag(
            "sh", ["-c", "npx --offline @mcp/server"]
        )

        assert "--offline" in args[1]
        # Should not have double --offline
        assert args[1].count("--offline") == 1

    def test_quoted_args_preserved(self):
        """Quoted arguments are preserved through shlex round-trip."""
        command, args = Sandbox._inject_offline_flag(
            "sh", ["-c", 'npx @mcp/server --name "my server"']
        )

        assert command == "sh"
        # Quoted arg should survive shlex parsing
        assert "my server" in args[1] or "'my server'" in args[1]

    def test_non_package_manager_unchanged(self):
        """Non-npx/uvx commands are not modified."""
        command, args = Sandbox._inject_offline_flag("node", ["server.js"])

        assert command == "node"
        assert args == ["server.js"]

    def test_docker_command_unchanged(self):
        """Docker commands are not modified (don't need --offline)."""
        command, args = Sandbox._inject_offline_flag(
            "docker", ["run", "image:tag", "/bin/sh"]
        )

        assert command == "docker"
        assert args == ["run", "image:tag", "/bin/sh"]

    def test_malformed_shell_command_skipped(self):
        """Malformed shell commands don't crash, just skip injection."""
        # Unbalanced quotes - shlex.split will fail
        command, args = Sandbox._inject_offline_flag(
            "sh", ["-c", 'npx @mcp/server --name "unterminated']
        )

        # Should return original without crashing
        assert command == "sh"
        assert args[0] == "-c"


class TestPathEscaping:
    """Tests for path escaping in seatbelt profiles."""

    def test_escape_newlines_in_path(self):
        """Newlines in paths are removed."""
        from src.sandboxes.impl.seatbelt import _escape_seatbelt_path

        result = _escape_seatbelt_path("/path/with\nnewline")
        assert "\n" not in result
        assert result == "/path/withnewline"

    def test_escape_carriage_return_in_path(self):
        """Carriage returns in paths are removed."""
        from src.sandboxes.impl.seatbelt import _escape_seatbelt_path

        result = _escape_seatbelt_path("/path/with\rcarriage")
        assert "\r" not in result

    def test_escape_quotes_in_path(self):
        """Quotes in paths are escaped."""
        from src.sandboxes.impl.seatbelt import _escape_seatbelt_path

        result = _escape_seatbelt_path('/path/with"quote')
        assert '\\"' in result

    def test_escape_backslash_in_path(self):
        """Backslashes in paths are escaped."""
        from src.sandboxes.impl.seatbelt import _escape_seatbelt_path

        result = _escape_seatbelt_path("/path/with\\backslash")
        assert "\\\\" in result
