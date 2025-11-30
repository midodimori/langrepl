from __future__ import annotations

import shutil
import sys
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from src.skills.factory import Skill

logger = get_logger(__name__)


class SkillsHandler:
    def __init__(self, session):
        self.session = session

    async def handle(self, skills: list[Skill]) -> None:
        try:
            if not skills:
                console.print_error("No skills available")
                console.print("")
                return

            await self._get_skill_selection(skills)

        except Exception as e:
            console.print_error(f"Error displaying skills: {e}")
            console.print("")
            logger.debug("Skill display error", exc_info=True)

    async def _get_skill_selection(self, skills: list[Skill]) -> None:
        current_index = 0
        expanded_indices: set = set()
        scroll_offset = 0
        window_size = 10

        text_control = FormattedTextControl(
            text=lambda: self._format_skill_list(
                skills, current_index, expanded_indices, scroll_offset, window_size
            ),
            focusable=True,
            show_cursor=False,
        )

        kb = KeyBindings()

        @kb.add(Keys.Up)
        def _(event):
            nonlocal current_index, scroll_offset
            if current_index > 0:
                current_index -= 1
                if current_index < scroll_offset:
                    scroll_offset = current_index

        @kb.add(Keys.Down)
        def _(event):
            nonlocal current_index, scroll_offset
            if current_index < len(skills) - 1:
                current_index += 1
                if current_index >= scroll_offset + window_size:
                    scroll_offset = current_index - window_size + 1

        @kb.add(Keys.Tab)
        def _(event):
            if current_index in expanded_indices:
                expanded_indices.remove(current_index)
            else:
                expanded_indices.add(current_index)

        @kb.add(Keys.ControlC)
        def _(event):
            event.app.exit()

        app: Application = Application(
            layout=Layout(Window(content=text_control)),
            key_bindings=kb,
            full_screen=False,
        )

        try:
            console.print("[muted]Tab: expand/collapse")
            console.print("")

            await app.run_async()

        except (KeyboardInterrupt, EOFError):
            pass  # Exit gracefully
        finally:
            num_visible = min(len(skills), window_size)
            num_lines = num_visible + 2
            for idx in expanded_indices:
                if scroll_offset <= idx < scroll_offset + window_size:
                    desc = skills[idx].description
                    terminal_width = shutil.get_terminal_size().columns
                    wrap_width = max(1, terminal_width - 6)
                    for desc_line in desc.split("\n"):
                        num_lines += 1 + (
                            len(desc_line) // wrap_width
                            if len(desc_line) > wrap_width
                            else 0
                        )
            for _i in range(num_lines):
                sys.stdout.write("\033[F")
                sys.stdout.write("\033[K")
            sys.stdout.flush()

    @staticmethod
    def _format_skill_list(
        skills: list[Skill],
        selected_index: int,
        expanded_indices: set,
        scroll_offset: int,
        window_size: int,
    ):
        prompt_symbol = settings.cli.prompt_style.strip()
        lines = []

        visible_skills = skills[scroll_offset : scroll_offset + window_size]

        for idx, skill in enumerate(visible_skills):
            i = scroll_offset + idx
            name = f"{skill.category}/{skill.name}"
            description = skill.description

            if i == selected_index:
                lines.append((f"{theme.selection_color}", f"{prompt_symbol} {name}"))
            else:
                lines.append(("", f"  {name}"))

            if i in expanded_indices:
                lines.append(("", "\n"))
                terminal_width = shutil.get_terminal_size().columns
                wrap_width = terminal_width - 6

                desc_lines = description.split("\n")
                for j, desc_line in enumerate(desc_lines):
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

            if idx < len(visible_skills) - 1:
                lines.append(("", "\n"))

        return FormattedText(lines)
