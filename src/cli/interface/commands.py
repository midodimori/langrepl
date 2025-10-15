"""Slash command parser and handlers."""

import shlex
import uuid
from collections.abc import Callable

from src.cli.initializer import initializer
from src.cli.interface.agents import AgentHandler
from src.cli.interface.compress import CompressionHandler
from src.cli.interface.graph import GraphHandler
from src.cli.interface.mcp import MCPHandler
from src.cli.interface.memory import MemoryHandler
from src.cli.interface.models import ModelHandler
from src.cli.interface.replay import ReplayHandler
from src.cli.interface.resume import ResumeHandler
from src.cli.interface.tools import ToolsHandler
from src.cli.theme import console


class CommandHandler:
    """Handle slash commands."""

    def __init__(self, session):
        """Initialize with reference to CLI session."""
        self.session = session
        self.commands = self._register_commands()
        self.resume_handler = ResumeHandler(session)
        self.agent_handler = AgentHandler(session)
        self.model_handler = ModelHandler(session)
        self.mcp_handler = MCPHandler(session)
        self.memory_handler = MemoryHandler(session)
        self.tools_handler = ToolsHandler(session)
        self.replay_handler = ReplayHandler(session)
        self.compression_handler = CompressionHandler(session)
        self.graph_handler = GraphHandler(session)

    def _register_commands(self) -> dict[str, Callable]:
        """Register all available commands."""
        return {
            "/help": self.cmd_help,
            "/agents": self.cmd_agents,
            "/model": self.cmd_model,
            "/tools": self.cmd_tools,
            "/mcp": self.cmd_mcp,
            "/memory": self.cmd_memory,
            "/graph": self.cmd_graph,
            "/clear": self.cmd_clear,
            "/exit": self.cmd_exit,
            "/resume": self.cmd_resume,
            "/replay": self.cmd_replay,
            "/compress": self.cmd_compress,
        }

    async def handle(self, command_line: str) -> str | None:
        """Handle a slash command.

        Returns:
            Optional prefilled text for the prompt
        """
        if not command_line.startswith("/"):
            console.print_error("Commands must start with '/'")
            return None

        # Parse command and arguments
        try:
            parts = shlex.split(command_line)
            if not parts:
                console.print_error("Empty command")
                return None

            command = parts[0].lower()
            args = parts[1:] if len(parts) > 1 else []

            # Execute command
            if command in self.commands:
                result = await self.commands[command](args)
                return result if isinstance(result, str) else None
            else:
                console.print_error(f"Unknown command: {command}")
                await self.cmd_help([])
                return None

        except Exception as e:
            console.print_error(f"Command error: {e}")
            return None

    async def cmd_help(self, args: list[str]) -> None:
        """Show help information."""
        self.session.renderer.render_help(self.commands)

    async def cmd_agents(self, args: list[str]) -> None:
        """Handle agents command with interactive selector."""
        await self.agent_handler.handle()

    async def cmd_model(self, args: list[str]) -> None:
        """Handle model command with interactive selector."""
        await self.model_handler.handle()

    async def cmd_tools(self, args: list[str]) -> None:
        """Handle tools command with interactive selector."""
        await self.tools_handler.handle(initializer.cached_tools)

    async def cmd_mcp(self, args: list[str]) -> None:
        """Handle MCP management command."""
        await self.mcp_handler.handle()

    async def cmd_memory(self, args: list[str]) -> None:
        """Open memory file for editing user preferences and context."""
        await self.memory_handler.handle()

    async def cmd_clear(self, args: list[str]) -> None:
        """Clear the screen and start a new thread."""
        new_thread_id = str(uuid.uuid4())
        self.session.update_context(
            thread_id=new_thread_id,
            current_input_tokens=None,
            current_output_tokens=None,
            total_cost=None,
        )
        console.clear()

    async def cmd_exit(self, args: list[str]) -> None:
        """Exit the application."""
        self.session.running = False

    async def cmd_resume(self, args: list[str]) -> None:
        """Resume conversation thread with interactive selector."""
        await self.resume_handler.handle()

    async def cmd_replay(self, args: list[str]) -> str | None:
        """Replay conversation from a previous human message."""
        return await self.replay_handler.handle()

    async def cmd_compress(self, args: list[str]) -> None:
        """Compress conversation history to a new thread."""
        await self.compression_handler.handle()

    async def cmd_graph(self, args: list[str]) -> None:
        """Render and display the current agent graph (use --browser to open in browser)."""
        # Validate and parse arguments
        if invalid_args := [arg for arg in args if arg != "--browser"]:
            console.print_error(f"Invalid argument(s): {', '.join(invalid_args)}")
            console.print("[muted]Usage: /graph [--browser][/muted]", markup=True)
            console.print("")
            return

        await self.graph_handler.handle(open_browser="--browser" in args)
