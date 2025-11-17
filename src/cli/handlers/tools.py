"""Tool handling for chat sessions."""

import shutil
import sys
from typing import Any

from prompt_toolkit.application import Application
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import FormattedTextControl

from src.cli.theme import console, theme
from src.core.logging import get_logger
from src.core.settings import settings

logger = get_logger(__name__)


class ToolsHandler:
    """Handles tool operations like listing and viewing details."""

    def __init__(self, session):
        """Initialize with reference to CLI session."""
        self.session = session

    async def handle(self, tools: list[Any]) -> None:
        """Show interactive tool selector and expand description on Enter."""
        try:
            if not tools:
                console.print_error("No tools available")
                console.print("")
                return

            # Show interactive tool selector
            await self._get_tool_selection(tools)

        except Exception as e:
            console.print_error(f"Error displaying tools: {e}")
            console.print("")
            logger.debug("Tool display error", exc_info=True)

    async def _get_tool_selection(self, tools: list[Any]) -> None:
        """Get tool selection from user using interactive list.

        Args:
            tools: List of tool objects

        Returns:
            None (just displays information)
        """
        if not tools:
            return

        current_index = 0
        expanded_indices: set = set()  # Track which tools are expanded
        scroll_offset = 0
        window_size = 10

        # Create text control with formatted text
        text_control = FormattedTextControl(
            text=lambda: self._format_tool_list(
                tools, current_index, expanded_indices, scroll_offset, window_size
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
            if current_index < len(tools) - 1:
                current_index += 1
                # Adjust scroll window if needed
                if current_index >= scroll_offset + window_size:
                    scroll_offset = current_index - window_size + 1

        @kb.add(Keys.Enter)
        def _(event):
            # Toggle expanded state
            if current_index in expanded_indices:
                expanded_indices.remove(current_index)
            else:
                expanded_indices.add(current_index)

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
            # Show helper text
            console.print("[muted]Enter: expand/collapse")
            console.print("")

            await app.run_async()

            # Calculate lines to clear (helper text + empty line + visible tools)
            num_visible = min(len(tools), window_size)
            # +2 for helper text and empty line
            num_lines = num_visible + 2
            for _i in range(num_lines):
                sys.stdout.write("\033[F")
                sys.stdout.write("\033[K")
            sys.stdout.flush()

        except (KeyboardInterrupt, EOFError):
            # Clear helper text + empty line + visible tools
            num_visible = min(len(tools), window_size)
            num_lines = num_visible + 2
            for _i in range(num_lines):
                sys.stdout.write("\033[F")
                sys.stdout.write("\033[K")
            sys.stdout.flush()

    @staticmethod
    def _format_tool_list(
        tools: list[Any],
        selected_index: int,
        expanded_indices: set,
        scroll_offset: int,
        window_size: int,
    ):
        """Format the tool list with highlighting and expansion.

        Args:
            tools: List of tool objects
            selected_index: Index of currently selected tool
            expanded_indices: Set of indices that should show full description
            scroll_offset: Starting index of visible window
            window_size: Number of items to display

        Returns:
            FormattedText with styled lines
        """
        prompt_symbol = settings.cli.prompt_style.strip()
        lines = []

        # Calculate visible range
        visible_tools = tools[scroll_offset : scroll_offset + window_size]

        for idx, tool in enumerate(visible_tools):
            i = scroll_offset + idx  # Actual index in the full list
            name = getattr(tool, "name", "Unknown")
            description = getattr(tool, "description", "No description")

            # Tool name line
            if i == selected_index:
                # Selected line with prompt symbol
                lines.append((f"{theme.selection_color}", f"{prompt_symbol} {name}"))
            else:
                # Regular line
                lines.append(("", f"  {name}"))

            # Show description if expanded
            if i in expanded_indices:
                lines.append(("", "\n"))
                # Format description with indentation and word wrapping
                terminal_width = shutil.get_terminal_size().columns
                wrap_width = terminal_width - 6  # Account for indentation

                desc_lines = description.split("\n")
                for j, desc_line in enumerate(desc_lines):
                    # Word wrap long lines
                    if len(desc_line) > wrap_width:
                        words = desc_line.split()
                        current_line = ""
                        for word in words:
                            if len(current_line) + len(word) + 1 <= wrap_width:
                                current_line += (word + " ") if current_line else word
                            else:
                                if current_line:
                                    lines.append(("dim", f"    {current_line}"))
                                    lines.append(("", "\n"))
                                current_line = word + " "
                        if current_line:
                            lines.append(("dim", f"    {current_line.rstrip()}"))
                    else:
                        lines.append(("dim", f"    {desc_line}"))

                    if j < len(desc_lines) - 1:
                        lines.append(("", "\n"))

            # Add newline between tools
            if idx < len(visible_tools) - 1:
                lines.append(("", "\n"))

        return FormattedText(lines)
