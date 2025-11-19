"""Thread resumption for chat sessions."""

import sys

from langchain_core.runnables import RunnableConfig
from prompt_toolkit.application import Application
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import FormattedTextControl

from src.cli.bootstrap.initializer import initializer
from src.cli.theme import console, theme
from src.core.logging import get_logger
from src.core.settings import settings
from src.utils.time import format_relative_time

logger = get_logger(__name__)


class ResumeHandler:
    """Handles resuming threads."""

    def __init__(self, session):
        """Initialize with reference to CLI session."""
        self.session = session

    async def handle(
        self, thread_id: str | None = None, render_history: bool = True
    ) -> None:
        """Show interactive thread selector and resume selected thread."""
        try:
            # If thread_id is provided, directly load that thread
            if thread_id:
                await self._load_thread(thread_id, render_history=render_history)
                return

            threads = await initializer.get_threads(
                self.session.context.agent, self.session.context.working_dir
            )

            # Filter out current thread from the list
            current_thread_id = self.session.context.thread_id
            threads = [
                thread
                for thread in threads
                if thread.get("thread_id") != current_thread_id
            ]

            if not threads:
                console.print_error("No other conversation threads found")
                console.print("")
                return

            # Show interactive thread selector
            selected_thread_id = await self._get_thread_selection(threads)

            if selected_thread_id:
                # Resume the selected thread and load its history
                await self._load_thread(
                    selected_thread_id, render_history=render_history
                )

        except Exception as e:
            console.print_error(f"Error resuming threads: {e}")
            console.print("")
            logger.debug("Thread resume error", exc_info=True)

    async def _get_thread_selection(self, threads: list[dict]) -> str:
        """Get thread selection from user using interactive list.

        Args:
            threads: List of thread dictionaries

        Returns:
            Selected thread ID or empty string if cancelled
        """
        if not threads:
            return ""

        current_index = 0
        window_size = 5
        scroll_offset = 0

        # Create text control with formatted text
        text_control = FormattedTextControl(
            text=lambda: self._format_thread_list(
                threads, current_index, scroll_offset, window_size
            ),
            focusable=True,
            show_cursor=False,
        )

        # Create key bindings
        kb = KeyBindings()

        @kb.add(Keys.Up)
        def _(event):
            nonlocal current_index, scroll_offset
            if current_index > 0:
                current_index -= 1
                # Adjust scroll window if needed
                if current_index < scroll_offset:
                    scroll_offset = current_index

        @kb.add(Keys.Down)
        def _(event):
            nonlocal current_index, scroll_offset
            if current_index < len(threads) - 1:
                current_index += 1
                # Adjust scroll window if needed
                if current_index >= scroll_offset + window_size:
                    scroll_offset = current_index - window_size + 1

        selected = [False]

        @kb.add(Keys.Enter)
        def _(event):
            selected[0] = True
            event.app.exit()

        @kb.add(Keys.ControlC)
        def _(event):
            event.app.exit()

        # Create application
        app: Application = Application(
            layout=Layout(Window(content=text_control)),
            key_bindings=kb,
            full_screen=False,
        )

        try:
            await app.run_async()

            # Clear the thread list from screen
            if selected[0]:
                # Calculate number of lines to clear (visible threads)
                num_lines = min(len(threads), window_size)
                # Move cursor up and clear lines
                for _i in range(num_lines):
                    sys.stdout.write("\033[F")  # Move cursor up one line
                    sys.stdout.write("\033[K")  # Clear line
                sys.stdout.flush()
                return threads[current_index].get("thread_id", "")

            console.print("")
            return ""

        except (KeyboardInterrupt, EOFError):
            console.print("")
            return ""

    @staticmethod
    def _format_thread_list(
        threads: list[dict], selected_index: int, scroll_offset: int, window_size: int
    ):
        """Format the thread list with highlighting and scrolling window.

        Args:
            threads: List of thread dictionaries
            selected_index: Index of currently selected thread
            scroll_offset: Starting index of visible window
            window_size: Number of items to display

        Returns:
            FormattedText with styled lines
        """
        prompt_symbol = settings.cli.prompt_style.strip()
        lines = []

        # Calculate visible range
        visible_threads = threads[scroll_offset : scroll_offset + window_size]

        for idx, thread in enumerate(visible_threads):
            i = scroll_offset + idx  # Actual index in the full list
            # Trim all newlines from the message preview
            raw_message = thread.get("last_message", "No messages").replace("\n", " ")
            last_message = raw_message[:60] + ("..." if len(raw_message) > 60 else "")
            timestamp = thread.get("timestamp", "")

            display_time = ""
            if timestamp:
                display_time = format_relative_time(timestamp)

            display_text = f"[{display_time}] {last_message}"

            if i == selected_index:
                # Use direct color code for selected line
                lines.append(
                    (f"{theme.selection_color}", f"{prompt_symbol} {display_text}")
                )
            else:
                lines.append(("", f"  {display_text}"))

            if idx < len(visible_threads) - 1:
                lines.append(("", "\n"))

        return FormattedText(lines)

    async def _load_thread(self, thread_id: str, render_history: bool = True) -> None:
        """Load and display conversation history for a thread."""
        try:
            # Get checkpointer directly from initializer
            async with initializer.get_checkpointer(
                self.session.context.agent, self.session.context.working_dir
            ) as checkpointer:
                # Create config for the specific thread
                config = RunnableConfig(
                    configurable={
                        "thread_id": thread_id,
                    }
                )

                # Get the latest checkpoint from the thread
                latest_checkpoint = await checkpointer.aget_tuple(config)
                if not latest_checkpoint:
                    console.print_error("No conversation history found for this thread")
                    console.print("")
                    return

                # Get channel values from the latest checkpoint
                latest_channel_values: dict = {}
                if (
                    latest_checkpoint.checkpoint
                    and "channel_values" in latest_checkpoint.checkpoint
                ):
                    latest_channel_values = latest_checkpoint.checkpoint[
                        "channel_values"
                    ]

                # Extract and render messages from the latest checkpoint
                # (Latest checkpoint contains full message history)
                if render_history:
                    messages = latest_channel_values.get("messages", [])
                    for message in messages:
                        self.session.renderer.render_message(message)

                # Restore context from latest checkpoint
                self.session.update_context(
                    thread_id=thread_id,
                    current_input_tokens=latest_channel_values.get(
                        "current_input_tokens"
                    ),
                    current_output_tokens=latest_channel_values.get(
                        "current_output_tokens"
                    ),
                    total_cost=latest_channel_values.get("total_cost"),
                )

        except Exception as e:
            console.print_error(f"Error loading thread history: {e}")
            console.print("")
            logger.debug("Thread history loading error", exc_info=True)
