"""Tests for CLI application entry point."""

from unittest.mock import patch

import pytest

from src.cli.bootstrap.app import cli, main


class TestMain:
    """Tests for main function."""

    @pytest.mark.asyncio
    async def test_main_routes_to_chat_by_default(
        self, patch_main_dependencies, mock_app_args
    ):
        """Test that main routes to chat command by default."""
        patch_main_dependencies["parser"].return_value.parse_args.return_value = (
            mock_app_args
        )

        result = await main()

        patch_main_dependencies["chat"].assert_called_once_with(mock_app_args)
        assert result == 0

    @pytest.mark.asyncio
    async def test_main_routes_to_server_when_flag_set(
        self, patch_main_dependencies, mock_app_args
    ):
        """Test that main routes to server command when --server flag is set."""
        mock_app_args.server = True
        patch_main_dependencies["parser"].return_value.parse_args.return_value = (
            mock_app_args
        )

        result = await main()

        patch_main_dependencies["server"].assert_called_once_with(mock_app_args)
        assert result == 0

    @pytest.mark.asyncio
    async def test_main_handles_exception(self, patch_main_dependencies, mock_app_args):
        """Test that main handles exceptions and returns error code."""
        patch_main_dependencies["parser"].return_value.parse_args.return_value = (
            mock_app_args
        )
        patch_main_dependencies["chat"].side_effect = Exception("Test error")

        result = await main()

        assert result == 1

    @pytest.mark.asyncio
    async def test_main_returns_nonzero_on_handler_failure(
        self, patch_main_dependencies, mock_app_args
    ):
        """Test that main returns non-zero when handler fails."""
        patch_main_dependencies["parser"].return_value.parse_args.return_value = (
            mock_app_args
        )
        patch_main_dependencies["chat"].return_value = 1

        result = await main()

        assert result == 1


class TestCli:
    """Tests for cli function."""

    @patch("src.cli.bootstrap.app.sys.exit")
    def test_cli_exits_with_return_code_zero(
        self,
        mock_exit,
        patch_main_dependencies,
        mock_app_args,
    ):
        """Test that cli exits with code 0 on success."""
        patch_main_dependencies["parser"].return_value.parse_args.return_value = (
            mock_app_args
        )

        cli()

        mock_exit.assert_called_once_with(0)

    @patch("src.cli.bootstrap.app.sys.exit")
    def test_cli_handles_keyboard_interrupt(
        self,
        mock_exit,
        patch_main_dependencies,
        mock_app_args,
    ):
        """Test that cli handles KeyboardInterrupt gracefully."""
        patch_main_dependencies["parser"].return_value.parse_args.return_value = (
            mock_app_args
        )
        patch_main_dependencies["chat"].side_effect = KeyboardInterrupt()

        cli()

        mock_exit.assert_called_once_with(0)

    @patch("src.cli.bootstrap.app.sys.exit")
    def test_cli_handles_exception(
        self,
        mock_exit,
        patch_main_dependencies,
        mock_app_args,
    ):
        """Test that cli handles exceptions and exits with code 1."""
        patch_main_dependencies["parser"].return_value.parse_args.return_value = (
            mock_app_args
        )
        patch_main_dependencies["chat"].side_effect = Exception("Test error")

        cli()

        mock_exit.assert_called_once_with(1)


@pytest.fixture
def patch_main_dependencies():
    """Patch create_parser and command handlers for main tests."""
    with (
        patch("src.cli.bootstrap.app.create_parser") as mock_parser,
        patch("src.cli.bootstrap.app.handle_chat_command", return_value=0) as mock_chat,
        patch(
            "src.cli.bootstrap.app.handle_server_command", return_value=0
        ) as mock_server,
    ):
        yield {
            "parser": mock_parser,
            "chat": mock_chat,
            "server": mock_server,
        }
