"""Tests for CLI application entry point."""

import os
from unittest.mock import patch

import pytest

from src.cli.bootstrap.app import cli, create_parser, main
from src.core.config import ApprovalMode


@pytest.fixture
def parser():
    """Create a parser for testing."""
    return create_parser()


class TestCreateParser:
    """Tests for create_parser function."""

    def test_create_parser_returns_parser(self, parser):
        """Test that create_parser returns an ArgumentParser."""
        assert parser is not None
        assert hasattr(parser, "parse_args")

    def test_create_parser_has_working_dir_argument(self, parser):
        """Test that parser has --working-dir argument."""
        args = parser.parse_args(["-w", "/test/path"])
        assert args.working_dir == "/test/path"

    def test_create_parser_working_dir_defaults_to_cwd(self, parser):
        """Test that --working-dir defaults to current directory."""
        args = parser.parse_args([])
        assert args.working_dir == os.getcwd()

    def test_create_parser_has_agent_argument(self, parser):
        """Test that parser has --agent argument."""
        args = parser.parse_args(["-a", "test-agent"])
        assert args.agent == "test-agent"

    def test_create_parser_agent_defaults_to_none(self, parser):
        """Test that --agent defaults to None."""
        args = parser.parse_args([])
        assert args.agent is None

    def test_create_parser_has_model_argument(self, parser):
        """Test that parser has --model argument."""
        args = parser.parse_args(["-m", "test-model"])
        assert args.model == "test-model"

    def test_create_parser_model_defaults_to_none(self, parser):
        """Test that --model defaults to None."""
        args = parser.parse_args([])
        assert args.model is None

    def test_create_parser_has_resume_flag(self, parser):
        """Test that parser has --resume flag."""
        args = parser.parse_args(["-r"])
        assert args.resume is True

    def test_create_parser_resume_defaults_to_false(self, parser):
        """Test that --resume defaults to False."""
        args = parser.parse_args([])
        assert args.resume is False

    def test_create_parser_has_timer_flag(self, parser):
        """Test that parser has --timer flag."""
        args = parser.parse_args(["-t"])
        assert args.timer is True

    def test_create_parser_timer_defaults_to_false(self, parser):
        """Test that --timer defaults to False."""
        args = parser.parse_args([])
        assert args.timer is False

    def test_create_parser_has_server_flag(self, parser):
        """Test that parser has --server flag."""
        args = parser.parse_args(["-s"])
        assert args.server is True

    def test_create_parser_server_defaults_to_false(self, parser):
        """Test that --server defaults to False."""
        args = parser.parse_args([])
        assert args.server is False

    def test_create_parser_has_approval_mode_argument(self, parser):
        """Test that parser has --approval-mode argument."""
        args = parser.parse_args(["-am", "active"])
        assert args.approval_mode == "active"

    def test_create_parser_approval_mode_defaults_to_semi_active(self, parser):
        """Test that --approval-mode defaults to semi_active."""
        args = parser.parse_args([])
        assert args.approval_mode == ApprovalMode.SEMI_ACTIVE.value

    def test_create_parser_validates_approval_mode_choices(self, parser):
        """Test that parser validates approval mode choices."""
        with pytest.raises(SystemExit):
            parser.parse_args(["-am", "invalid"])

    def test_create_parser_accepts_all_approval_modes(self, parser):
        """Test that parser accepts all valid approval modes."""
        for mode in ApprovalMode:
            args = parser.parse_args(["-am", mode.value])
            assert args.approval_mode == mode.value

    def test_create_parser_short_flags_work(self, parser):
        """Test that short flags work correctly."""
        args = parser.parse_args(
            [
                "-w",
                "/test",
                "-a",
                "agent",
                "-m",
                "model",
                "-r",
                "-t",
                "-s",
                "-am",
                "active",
            ]
        )

        assert args.working_dir == "/test"
        assert args.agent == "agent"
        assert args.model == "model"
        assert args.resume is True
        assert args.timer is True
        assert args.server is True
        assert args.approval_mode == "active"

    def test_create_parser_long_flags_work(self, parser):
        """Test that long flags work correctly."""
        args = parser.parse_args(
            [
                "--working-dir",
                "/test",
                "--agent",
                "agent",
                "--model",
                "model",
                "--resume",
                "--timer",
                "--server",
                "--approval-mode",
                "active",
            ]
        )

        assert args.working_dir == "/test"
        assert args.agent == "agent"
        assert args.model == "model"
        assert args.resume is True
        assert args.timer is True
        assert args.server is True
        assert args.approval_mode == "active"


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
    async def test_main_returns_zero_on_success(
        self, patch_main_dependencies, mock_app_args
    ):
        """Test that main returns 0 on success."""
        patch_main_dependencies["parser"].return_value.parse_args.return_value = (
            mock_app_args
        )

        result = await main()

        assert result == 0

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
    def test_cli_exits_with_return_code_one(
        self,
        mock_exit,
        patch_main_dependencies,
        mock_app_args,
    ):
        """Test that cli exits with code 1 on handler failure."""
        patch_main_dependencies["parser"].return_value.parse_args.return_value = (
            mock_app_args
        )
        patch_main_dependencies["chat"].return_value = 1

        cli()

        mock_exit.assert_called_once_with(1)

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
