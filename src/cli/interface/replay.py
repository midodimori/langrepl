"""Replay handling for conversation history."""

import sys

from langchain_core.messages import AnyMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from prompt_toolkit.application import Application
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import FormattedTextControl

from src.checkpointer.utils import delete_checkpoints_after, get_checkpoint_history
from src.cli.initializer import initializer
from src.cli.theme import console, theme
from src.core.logging import get_logger
from src.core.settings import settings

logger = get_logger(__name__)


class ReplayHandler:
    """Handles replaying conversation from a previous human message."""

    def __init__(self, session):
        """Initialize with reference to CLI session."""
        self.session = session

    async def handle(self) -> str | None:
        """Show interactive human message selector and replay from selected point.

        Returns:
            The selected human message text to prefill, or None if canceled.
        """
        try:
            # Get human messages from the current thread
            human_messages = await self._get_human_messages()

            if not human_messages:
                console.print_error("No previous messages found in this conversation")
                console.print("")
                return None

            # Show interactive selector
            selected_index = await self._get_message_selection(human_messages)

            if selected_index is not None:
                checkpoint_id = await self._replay_from_message(
                    human_messages, selected_index
                )

                # Delete all checkpoints after the selected one to rewind the thread
                try:
                    async with initializer.get_checkpointer(
                        self.session.context.agent, self.session.context.working_dir
                    ) as checkpointer:
                        await delete_checkpoints_after(
                            checkpointer, self.session.context.thread_id, checkpoint_id
                        )
                except Exception as e:
                    logger.error(f"Failed to delete checkpoints: {e}")
                    console.print_error(
                        f"Warning: Could not rewind conversation history: {e}"
                    )

                return human_messages[selected_index]["text"]

            return None

        except Exception as e:
            console.print_error(f"Error replaying conversation: {e}")
            logger.debug("Replay error", exc_info=True)
            return None

    async def _get_human_messages(self) -> list[dict]:
        """Get all human messages from current branch's checkpoint history.

        Returns:
            List of dicts with message info: {text, all_messages_before, channel_values, checkpoint_id}
        """
        async with initializer.get_checkpointer(
            self.session.context.agent, self.session.context.working_dir
        ) as checkpointer:
            config = RunnableConfig(
                configurable={"thread_id": self.session.context.thread_id}
            )

            latest_checkpoint = await checkpointer.aget_tuple(config)
            if not latest_checkpoint:
                return []

            checkpoint_history = await get_checkpoint_history(
                checkpointer, latest_checkpoint
            )
            history = []
            for checkpoint_tuple in checkpoint_history:
                checkpoint = checkpoint_tuple.checkpoint

                if checkpoint and "channel_values" in checkpoint:
                    channel_values = checkpoint["channel_values"]
                    messages = channel_values.get("messages", [])

                    if messages:
                        history.append(
                            {
                                "messages": messages,
                                "channel_values": channel_values,
                                "checkpoint_id": checkpoint.get("id"),
                            }
                        )

            # Track human messages and the checkpoint BEFORE each one
            human_messages = []
            prev_checkpoint_id = None
            prev_messages: list[AnyMessage] = []
            prev_channel_values: dict = {}

            for entry in history:
                current_messages = entry["messages"]
                current_checkpoint_id = entry["checkpoint_id"]

                # Find NEW messages in this checkpoint (not in previous)
                prev_message_ids = {
                    getattr(m, "id", None) or id(m) for m in prev_messages
                }

                has_new_messages = False
                for msg in current_messages:
                    message_id = getattr(msg, "id", None) or id(msg)
                    # This is a new message added in this checkpoint
                    if message_id not in prev_message_ids:
                        has_new_messages = True
                        if isinstance(msg, HumanMessage):
                            human_messages.append(
                                {
                                    "text": msg.text,
                                    "all_messages_before": prev_messages.copy(),
                                    "channel_values": prev_channel_values,
                                    "checkpoint_id": prev_checkpoint_id,
                                }
                            )

                # Only update tracking if this checkpoint had new messages
                if has_new_messages:
                    prev_checkpoint_id = current_checkpoint_id
                    prev_messages = current_messages
                    prev_channel_values = entry["channel_values"]

            return human_messages

    async def _get_message_selection(self, messages: list[dict]) -> int | None:
        """Get message selection from user using interactive list.

        Args:
            messages: List of human message dictionaries

        Returns:
            Selected message index or None if cancelled
        """
        if not messages:
            return None

        window_size = 5
        # Start at the latest message (last in the list)
        current_index = len(messages) - 1
        # Position scroll window to show the latest messages
        scroll_offset = max(0, len(messages) - window_size)

        text_control = FormattedTextControl(
            text=lambda: self._format_message_list(
                messages, current_index, scroll_offset, window_size
            ),
            focusable=True,
            show_cursor=False,
        )

        kb = KeyBindings()

        @kb.add(Keys.Up)
        def _(_event):
            nonlocal current_index, scroll_offset
            if current_index > 0:
                current_index -= 1
                if current_index < scroll_offset:
                    scroll_offset = current_index

        @kb.add(Keys.Down)
        def _(_event):
            nonlocal current_index, scroll_offset
            if current_index < len(messages) - 1:
                current_index += 1
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

        app: Application = Application(
            layout=Layout(Window(content=text_control)),
            key_bindings=kb,
            full_screen=False,
        )

        try:
            await app.run_async()

            if selected[0]:
                # Clear the selector from screen
                num_lines = min(len(messages), window_size)
                for _i in range(num_lines):
                    sys.stdout.write("\033[F")
                    sys.stdout.write("\033[K")
                sys.stdout.flush()
                return current_index

            console.print("")
            return None

        except (KeyboardInterrupt, EOFError):
            console.print("")
            return None

    @staticmethod
    def _format_message_list(
        messages: list[dict], selected_index: int, scroll_offset: int, window_size: int
    ):
        """Format the message list with highlighting and scrolling window."""
        prompt_symbol = settings.cli.prompt_style.strip()
        lines = []

        visible_messages = messages[scroll_offset : scroll_offset + window_size]

        for idx, message in enumerate(visible_messages):
            i = scroll_offset + idx
            # Trim and truncate the message text
            raw_text = message["text"].replace("\n", " ")
            display_text = raw_text[:80] + ("..." if len(raw_text) > 80 else "")

            if i == selected_index:
                lines.append(
                    (f"{theme.selection_color}", f"{prompt_symbol} {display_text}")
                )
            else:
                lines.append(("", f"  {display_text}"))

            if idx < len(visible_messages) - 1:
                lines.append(("", "\n"))

        return FormattedText(lines)

    async def _replay_from_message(
        self, human_messages: list[dict], selected_index: int
    ) -> str | None:
        """Clear screen, re-render history, return checkpoint_id to replay from.

        Args:
            human_messages: List of human message dictionaries (oldest first)
            selected_index: Index of selected message in the list

        Returns:
            The checkpoint_id to fork from, or None if not available
        """
        try:
            # Get the selected message entry
            selected_entry = human_messages[selected_index]
            messages_to_render = selected_entry["all_messages_before"]
            checkpoint_id = selected_entry.get("checkpoint_id")

            # Clear the screen
            console.clear()

            # Render all messages up to (but not including) the selected point
            rendered_message_ids = set()

            for message in messages_to_render:
                message_id = getattr(message, "id", None) or id(message)
                if message_id not in rendered_message_ids:
                    rendered_message_ids.add(message_id)
                    self.session.renderer.render_message(message)

            # Update context with the channel values from this point
            channel_values = selected_entry["channel_values"]
            self.session.update_context(
                current_input_tokens=channel_values.get("current_input_tokens"),
                current_output_tokens=channel_values.get("current_output_tokens"),
                total_cost=channel_values.get("total_cost"),
            )

            return checkpoint_id

        except Exception as e:
            console.print_error(f"Error replaying history: {e}")
            logger.debug("History replay error", exc_info=True)
            return None
