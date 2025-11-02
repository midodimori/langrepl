"""Interactive chat session management."""

from contextlib import AbstractAsyncContextManager

from langgraph.graph.state import CompiledStateGraph

from src.cli.core.context import Context
from src.cli.initializer import initializer
from src.cli.interface.commands import CommandHandler
from src.cli.interface.messages import MessageHandler
from src.cli.interface.prompt import InteractivePrompt
from src.cli.interface.renderer import Renderer
from src.cli.theme import console, theme
from src.core.logging import get_logger

logger = get_logger(__name__)


class CLISession:
    """Main CLI session manager for interactive chat."""

    def __init__(
        self,
        context: Context,
    ):
        self.context = context
        self.renderer = Renderer()
        self.command_handler = CommandHandler(self)
        self.message_handler = MessageHandler(self)
        self.prompt = InteractivePrompt(
            self.context, list(self.command_handler.commands.keys()), session=self
        )

        # Set up mode change callback
        self.prompt.set_mode_change_callback(self._handle_approval_mode_change)

        # Session state
        self.graph: CompiledStateGraph | None = None
        self.graph_context: AbstractAsyncContextManager[CompiledStateGraph] | None = (
            None
        )
        self.running = False
        self.needs_reload = False
        self.prefilled_text: str | None = None

    async def start(self, show_welcome: bool = True) -> None:
        """Start the interactive session."""
        self.graph_context = initializer.get_graph(
            agent=self.context.agent,
            model=self.context.model,
            working_dir=self.context.working_dir,
        )
        with console.console.status(
            f"[{theme.spinner_color}]Loading...[/{theme.spinner_color}]"
        ) as status:
            async with self.graph_context as graph:
                self.graph = graph
                status.stop()
                if show_welcome:
                    self.renderer.show_welcome(self.context)
                await self._main_loop()

    async def _main_loop(self) -> None:
        """Main interactive loop."""
        self.running = True

        while self.running:
            try:
                content, short_content, is_slash_command = await self.prompt.get_input()

                if not content or not content.strip():
                    continue

                if is_slash_command:
                    result = await self.command_handler.handle(content)
                    if result:
                        self.prefilled_text = result
                    continue

                await self.message_handler.handle(content, short_content)

            except EOFError:
                break
            except Exception as e:
                console.print_error(f"Error processing input: {e}")
                logger.debug("Input processing error")

    def update_context(self, **kwargs) -> None:
        """Update context fields dynamically.

        Args:
            **kwargs: Context fields to update (thread_id, agent, model,
                     current_input_tokens, current_output_tokens, total_cost, etc.)
        """
        # Fields that trigger reload
        if "agent" in kwargs or "model" in kwargs:
            self.needs_reload = True
            self.running = False

        # Update all fields
        for key, value in kwargs.items():
            if hasattr(self.context, key):
                setattr(self.context, key, value)

    def _handle_approval_mode_change(self) -> None:
        """Handle approval mode cycling from keyboard shortcut."""
        self.context.cycle_approval_mode()
        # Refresh the prompt style to reflect the new mode
        self.prompt.refresh_style()
