"""Replay handling for conversation history."""

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

logger = get_logger(__name__)


class ReplayHandler:
    """Handles replaying conversation from a previous human message."""

    def __init__(self, session):
        """Initialize with reference to CLI session."""
        self.session = session

    async def handle(self) -> None:
        """Show interactive human message selector and replay from selected point."""
        try:
            # Get human messages from the current thread
            human_messages, all_messages = await self._get_human_messages()

            if not human_messages:
                console.print_error("No previous messages found in this conversation")
                console.print("")
                return None

            # Show interactive selector
            selected_index = await self._get_message_selection(human_messages)

            if selected_index is not None:
                try:
                    checkpoint_id = await self._replay_from_message(
                        human_messages, all_messages, selected_index
                    )
                except Exception as e:
                    console.print_error(f"Error replaying history: {e}")
                    console.print("")
                    logger.debug("History replay error", exc_info=True)
                    return None

                try:
                    with console.console.status(
                        f"[{theme.spinner_color}]Rewinding...[/{theme.spinner_color}]"
                    ):
                        async with initializer.get_checkpointer(
                            self.session.context.agent, self.session.context.working_dir
                        ) as checkpointer:
                            await checkpointer.delete_after(
                                self.session.context.thread_id, checkpoint_id
                            )

                            config = RunnableConfig(
                                configurable={
                                    "thread_id": self.session.context.thread_id
                                }
                            )
                            rewound_checkpoint = await checkpointer.aget_tuple(config)
                            if rewound_checkpoint and rewound_checkpoint.checkpoint:
                                channel_values = rewound_checkpoint.checkpoint.get(
                                    "channel_values", {}
                                )
                                self.session.update_context(
                                    current_input_tokens=channel_values.get(
                                        "current_input_tokens"
                                    ),
                                    current_output_tokens=channel_values.get(
                                        "current_output_tokens"
                                    ),
                                    total_cost=channel_values.get("total_cost"),
                                )
                except Exception as e:
                    logger.error(f"Failed to delete checkpoints: {e}")
                    console.print_error(
                        f"Warning: Could not rewind conversation history: {e}"
                    )
                    console.print("")

                selected_message = human_messages[selected_index]
                self.session.prefilled_text = selected_message.text
                self.session.prefilled_reference_mapping = (
                    selected_message.reference_mapping
                )

            return None

        except Exception as e:
            console.print_error(f"Error replaying conversation: {e}")
            console.print("")
            logger.debug("Replay error", exc_info=True)
            return None

    async def _get_human_messages(self):
        """Get all human messages from current thread."""
        async with initializer.get_checkpointer(
            self.session.context.agent, self.session.context.working_dir
        ) as checkpointer:
            thread_id = self.session.context.thread_id

            config = RunnableConfig(configurable={"thread_id": thread_id})
            latest = await checkpointer.aget_tuple(config)

            if not latest:
                return [], []

            with console.console.status(
                f"[{theme.spinner_color}]Loading...[/{theme.spinner_color}]"
            ) as status:

                def on_indexing():
                    status.update(
                        f"[{theme.spinner_color}]Indexing once...[/{theme.spinner_color}]"
                    )

                return await checkpointer.get_human_messages(
                    thread_id, latest, on_indexing=on_indexing
                )

    async def _get_message_selection(self, messages) -> int | None:
        """Get message selection from user using interactive list.

        Args:
            messages: List of HumanMessageEntry objects

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
        messages, selected_index: int, scroll_offset: int, window_size: int
    ):
        """Format the message list with highlighting and scrolling window."""
        prompt_symbol = settings.cli.prompt_style.strip()
        lines = []

        visible_messages = messages[scroll_offset : scroll_offset + window_size]

        for idx, message in enumerate(visible_messages):
            i = scroll_offset + idx
            # Trim and truncate the message text
            raw_text = message.text.replace("\n", " ")
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
        self, human_messages, all_messages, selected_index: int
    ) -> str | None:
        """Clear screen, re-render history, return checkpoint_id to replay from.

        Returns:
            checkpoint_id to delete from (None means delete all for first message)

        Raises:
            Exception if replay fails
        """
        selected_entry = human_messages[selected_index]
        console.clear()

        messages_before = all_messages[: selected_entry.messages_before_count]

        rendered_ids = set()
        for message in messages_before:
            msg_id = getattr(message, "id", None) or id(message)
            if msg_id not in rendered_ids:
                rendered_ids.add(msg_id)
                self.session.renderer.render_message(message)

        return selected_entry.checkpoint_id
