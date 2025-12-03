"""Interactive chat session management."""

from __future__ import annotations

import asyncio
import signal
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from types import FrameType
from typing import TYPE_CHECKING, Any

from src.cli.bootstrap.initializer import initializer
from src.cli.dispatchers import CommandDispatcher, MessageDispatcher
from src.cli.handlers.bash import BashDispatcher
from src.cli.theme import console, theme
from src.cli.ui.prompt import InteractivePrompt
from src.cli.ui.renderer import Renderer
from src.core.logging import get_logger
from src.utils.version import check_for_updates

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph

    from src.cli.core.context import Context

SignalHandler = Callable[[int, FrameType | None], Any] | int | None

logger = get_logger(__name__)


class Session:
    """Main CLI session manager for interactive chat."""

    def __init__(
        self,
        context: Context,
    ):
        self.context = context
        self.renderer = Renderer()
        self.command_dispatcher = CommandDispatcher(self)
        self.message_dispatcher = MessageDispatcher(self)
        self.bash_dispatcher = BashDispatcher(self)
        self.prompt = InteractivePrompt(
            self.context, list(self.command_dispatcher.commands.keys()), session=self
        )

        # Set up mode change callbacks
        self.prompt.set_mode_change_callback(self._handle_approval_mode_change)
        self.prompt.set_bash_mode_toggle_callback(self._handle_bash_mode_toggle)

        # Session state
        self.graph: CompiledStateGraph | None = None
        self.graph_context: AbstractAsyncContextManager[CompiledStateGraph] | None = (
            None
        )
        self.running = False
        self.needs_reload = False
        self.prefilled_text: str | None = None
        self.prefilled_reference_mapping: dict[str, str] = {}
        self.current_stream_task: asyncio.Task | None = None
        self._sigint_registered = False
        self._previous_sigint: SignalHandler = None

    async def start(self, show_welcome: bool = True) -> None:
        """Start the interactive session."""
        try:
            self.graph_context = initializer.get_graph(
                agent=self.context.agent,
                model=self.context.model,
                working_dir=self.context.working_dir,
            )

            self._register_sigint_handler()

            with console.console.status(
                f"[{theme.spinner_color}]Loading...[/{theme.spinner_color}]"
            ) as status:
                async with self.graph_context as graph:
                    self.graph = graph
                    status.stop()
                    if show_welcome:
                        console.print("")
                        self.renderer.show_welcome(self.context)

                        # Check for updates
                        updates = check_for_updates()
                        if updates:
                            latest_version, upgrade_command = updates
                            if latest_version and upgrade_command:
                                console.print_warning(
                                    f"[muted]New version available ({latest_version}). Upgrade with: [muted.bold]uv tool install langrepl --upgrade[/muted.bold][/muted]"
                                )
                                console.print("")

                    await self._main_loop()
        finally:
            self._restore_sigint()

    async def _main_loop(self) -> None:
        """Main interactive loop."""
        self.running = True

        while self.running:
            try:
                content, is_slash_command = await self.prompt.get_input()

                if not content:
                    continue

                if self.context.bash_mode:
                    await self.bash_dispatcher.dispatch(content)
                    continue

                if is_slash_command:
                    await self.command_dispatcher.dispatch(content)
                    continue

                await self.message_dispatcher.dispatch(content)

            except EOFError:
                break
            except Exception as e:
                console.print_error(f"Error processing input: {e}")
                console.print("")
                logger.debug("Input processing error")

    async def send(self, message: str) -> int:
        """Send a single message in one-shot mode (non-interactive)."""
        try:
            self.graph_context = initializer.get_graph(
                agent=self.context.agent,
                model=self.context.model,
                working_dir=self.context.working_dir,
            )

            self._register_sigint_handler()

            async with self.graph_context as graph:
                self.graph = graph
                await self.message_dispatcher.dispatch(message)
                return 0

        except KeyboardInterrupt:
            return 0
        except Exception as e:
            console.print_error(f"Error sending message: {e}")
            console.print("")
            logger.exception("CLI message error")
            return 1
        finally:
            self._restore_sigint()

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

    def _handle_bash_mode_toggle(self) -> None:
        """Handle bash mode toggle from keyboard shortcut."""
        self.context.toggle_bash_mode()
        # Refresh the prompt style to reflect the new mode
        self.prompt.refresh_style()

    def _register_sigint_handler(self) -> None:
        """Install SIGINT handler that cancels the active stream before exit.

        Contract: first Ctrl+C cancels any in-flight stream task; subsequent
        Ctrl+C follows the previous handler (which, in interactive mode, is the
        prompt's double-press-to-quit logic). One-shot and interactive paths
        share this handler to keep behavior consistent.
        """
        if self._sigint_registered:
            return

        try:
            self._previous_sigint = signal.getsignal(signal.SIGINT)

            def _handle_sigint(signum, frame):
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if (
                    loop
                    and self.current_stream_task
                    and not self.current_stream_task.done()
                ):
                    loop.call_soon_threadsafe(self.current_stream_task.cancel)
                    return

                if callable(self._previous_sigint):
                    self._previous_sigint(signum, frame)
                    return

                if self._previous_sigint == signal.SIG_IGN:
                    return

                raise KeyboardInterrupt()

            signal.signal(signal.SIGINT, _handle_sigint)
            self._sigint_registered = True
        except Exception as e:
            logger.exception("Failed to register SIGINT handler", exc_info=e)

    def _restore_sigint(self) -> None:
        """Restore previous SIGINT handler if we overrode it."""
        if not self._sigint_registered:
            return

        # TODO: Verify SIGINT restoration logic where handlers may differ.
        # if self._previous_sigint is not None:
        #     try:
        #         signal.signal(signal.SIGINT, self._previous_sigint)
        #     except Exception:
        #         pass
        try:
            signal.signal(
                signal.SIGINT,
                (
                    self._previous_sigint
                    if self._previous_sigint is not None
                    else signal.SIG_DFL
                ),
            )
        except Exception:
            pass

        self._sigint_registered = False
