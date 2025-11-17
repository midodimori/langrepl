"""Main CLI application entry point."""

import argparse
import asyncio
import os
import sys

from src.cli.bootstrap.chat import handle_chat_command
from src.cli.bootstrap.server import handle_server_command
from src.cli.theme import console
from src.core.config import ApprovalMode
from src.core.constants import APP_NAME
from src.core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


def create_parser() -> argparse.ArgumentParser:
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description="Interactive command-line chat application powered by Langchain, Langgraph, Prompt Toolkit and Rich",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Add positional message argument for one-shot mode
    parser.add_argument(
        "message",
        type=str,
        nargs="?",
        default=None,
        help="Message to send in one-shot mode (omit for interactive mode)",
    )

    # Add global working directory option
    parser.add_argument(
        "-w",
        "--working-dir",
        type=str,
        default=os.getcwd(),
        help="Working directory for the session (default: current directory)",
    )

    # Add chat arguments directly to main parser
    parser.add_argument(
        "-a",
        "--agent",
        type=str,
        default=None,
        help="Agent to use for the session (uses default agent from config if not specified)",
    )
    parser.add_argument(
        "-m",
        "--model",
        type=str,
        default=None,
        help="LLM model to use for the session (overrides agent's default model if specified)",
    )
    parser.add_argument(
        "-r",
        "--resume",
        action="store_true",
        help="Resume the last conversation thread",
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
        help="Run in LangGraph server mode (generates langgraph.json and runs langgraph dev)",
    )
    parser.add_argument(
        "-am",
        "--approval-mode",
        type=str,
        choices=[mode.value for mode in ApprovalMode],
        default=ApprovalMode.SEMI_ACTIVE.value,
        help=f"Tool approval mode ({', '.join(mode.value for mode in ApprovalMode)})",
    )

    return parser


async def main() -> int:
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()

    try:
        # Route to server mode if -s flag is present
        if args.server:
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
