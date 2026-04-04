"""Main CLI application entry point."""

import argparse
import asyncio
import os
import sys
from pathlib import Path

from langrepl.cli.bootstrap.chat import handle_chat_command
from langrepl.cli.bootstrap.server import handle_server_command
from langrepl.cli.theme import console
from langrepl.configs import ApprovalMode
from langrepl.core.constants import APP_NAME
from langrepl.core.logging import configure_logging, get_logger


def create_parser() -> argparse.ArgumentParser:
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description="Interactive command-line chat application powered by Langchain, Langgraph, Prompt Toolkit and Rich",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "message",
        type=str,
        nargs="?",
        default=None,
        help="Message to send in one-shot mode (chat mode only)",
    )
    parser.add_argument(
        "-w",
        "--working-dir",
        type=str,
        default=os.getcwd(),
        help="Working directory for the session (default: current directory)",
    )
    parser.add_argument(
        "-a",
        "--agent",
        type=str,
        default=None,
        help="Agent to use. In server mode: serve only this agent (default: serve all)",
    )
    parser.add_argument(
        "-m",
        "--model",
        type=str,
        default=None,
        help="LLM model override. In server mode: requires -a",
    )
    parser.add_argument(
        "-r",
        "--resume",
        action="store_true",
        help="Resume the last conversation thread (chat mode only)",
    )
    parser.add_argument(
        "-t",
        "--timer",
        action="store_true",
        help="Enable performance timing for startup phases",
    )
    parser.add_argument(
        "-s",
        "--server",
        action="store_true",
        help="Run as HTTP server (protocol from config.server.yml)",
    )
    parser.add_argument(
        "-am",
        "--approval-mode",
        type=str,
        choices=[mode.value for mode in ApprovalMode],
        default=ApprovalMode.SEMI_ACTIVE.value,
        help="Tool approval mode. In server mode: requires -a",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging to console and .langrepl/app.log",
    )

    return parser


def _validate_server_args(parser: argparse.ArgumentParser, args) -> None:
    """Validate flag combinations for server mode."""
    if args.resume:
        parser.error("--resume is not available in server mode")
    if args.message:
        parser.error("one-shot messages are not supported in server mode")
    if args.model and not args.agent:
        parser.error("--model requires --agent (-a) in server mode")
    if args.approval_mode != ApprovalMode.SEMI_ACTIVE.value and not args.agent:
        parser.error("--approval-mode requires --agent (-a) in server mode")


async def main() -> int:
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()

    configure_logging(show_logs=args.verbose, working_dir=Path(args.working_dir))
    logger = get_logger(__name__)

    try:
        if args.server:
            _validate_server_args(parser, args)
            return await handle_server_command(args)
        else:
            return await handle_chat_command(args)
    except Exception as e:
        console.print_error(f"Unexpected error: {e}")
        console.print("")
        logger.exception("CLI error")
        return 1


def cli():
    """Synchronous CLI entry point for setuptools."""
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    cli()
