"""Approval rules handler for managing tool approval lists."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from prompt_toolkit.application import Application
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl

from langrepl.cli.theme import console, theme
from langrepl.cli.ui.shared import (
    create_bottom_toolbar,
    create_instruction,
    create_prompt_style,
)
from langrepl.configs import ToolApprovalConfig, ToolApprovalRule
from langrepl.core.constants import CONFIG_APPROVAL_FILE_NAME
from langrepl.core.logging import get_logger
from langrepl.core.settings import settings

logger = get_logger(__name__)

# Tab names for the three lists
TAB_NAMES = ["always_deny", "always_ask", "always_allow"]


class ApproveHandler:
    """Handles approval rules management with tabbed UI."""

    def __init__(self, session) -> None:
        """Initialize with reference to CLI session."""
        self.session = session

    async def handle(self) -> None:
        """Show interactive tabbed approval rules manager."""
        try:
            config_file = (
                Path(self.session.context.working_dir) / CONFIG_APPROVAL_FILE_NAME
            )
            approval_config = ToolApprovalConfig.from_json_file(config_file)

            await self._show_tabbed_ui(approval_config, config_file)

        except Exception as e:
            console.print_error(f"Error managing approval rules: {e}")
            console.print("")
            logger.debug("Approval rules error", exc_info=True)

    async def _show_tabbed_ui(
        self, config: ToolApprovalConfig, config_file: Path
    ) -> None:
        """Show tabbed UI for managing approval rules."""
        current_tab_idx = 0
        current_rule_idx = 0
        open_editor = [False]

        def get_rules_for_tab(tab_idx: int) -> list[ToolApprovalRule]:
            if tab_idx == 0:
                return config.always_deny
            elif tab_idx == 1:
                return config.always_ask
            else:
                return config.always_allow

        def set_rules_for_tab(tab_idx: int, rules: list[ToolApprovalRule]) -> None:
            if tab_idx == 0:
                config.always_deny = rules
            elif tab_idx == 1:
                config.always_ask = rules
            else:
                config.always_allow = rules

        text_control = FormattedTextControl(
            text=lambda: self._format_tabbed_rules_list(
                config, current_tab_idx, current_rule_idx
            ),
            focusable=True,
            show_cursor=False,
        )

        kb = KeyBindings()

        @kb.add(Keys.Tab)
        def _(event):
            nonlocal current_tab_idx, current_rule_idx
            current_tab_idx = (current_tab_idx + 1) % len(TAB_NAMES)
            current_rule_idx = 0

        @kb.add(Keys.BackTab)
        def _(event):
            nonlocal current_tab_idx, current_rule_idx
            current_tab_idx = (current_tab_idx - 1) % len(TAB_NAMES)
            current_rule_idx = 0

        @kb.add(Keys.Up)
        def _(event):
            nonlocal current_rule_idx
            rules = get_rules_for_tab(current_tab_idx)
            if rules and current_rule_idx > 0:
                current_rule_idx -= 1

        @kb.add(Keys.Down)
        def _(event):
            nonlocal current_rule_idx
            rules = get_rules_for_tab(current_tab_idx)
            if rules and current_rule_idx < len(rules) - 1:
                current_rule_idx += 1

        @kb.add("d")
        def _(event):
            nonlocal current_rule_idx
            rules = get_rules_for_tab(current_tab_idx)
            if rules and 0 <= current_rule_idx < len(rules):
                rules.pop(current_rule_idx)
                set_rules_for_tab(current_tab_idx, rules)
                config.save_to_json_file(config_file)
                if current_rule_idx >= len(rules) and len(rules) > 0:
                    current_rule_idx = len(rules) - 1

        @kb.add("e")
        def _(event):
            open_editor[0] = True
            event.app.exit()

        @kb.add(Keys.ControlC)
        def _(event):
            event.app.exit()

        context = self.session.context
        app: Application = Application(
            layout=Layout(
                HSplit(
                    [
                        *create_instruction(
                            "Tab/Shift+Tab: switch, d: delete, e: edit"
                        ),
                        Window(content=text_control),
                        Window(
                            height=1,
                            content=FormattedTextControl(
                                lambda: create_bottom_toolbar(
                                    context,
                                    context.working_dir,
                                    bash_mode=context.bash_mode,
                                )
                            ),
                        ),
                    ]
                )
            ),
            key_bindings=kb,
            full_screen=False,
            style=create_prompt_style(context, bash_mode=context.bash_mode),
            erase_when_done=True,
        )

        try:
            await app.run_async()
        except (KeyboardInterrupt, EOFError):
            pass

        if open_editor[0]:
            self._open_in_editor(config_file)

    def _format_tabbed_rules_list(
        self,
        config: ToolApprovalConfig,
        selected_tab_idx: int,
        selected_rule_idx: int,
    ) -> FormattedText:
        """Format tabbed rules list with tabs and rule entries."""
        prompt_symbol = settings.cli.prompt_style.strip()
        term_width = shutil.get_terminal_size().columns

        lines: list[tuple[str, str]] = []

        # Tab bar
        current_line_len = 0
        for i, tab_name in enumerate(TAB_NAMES):
            is_selected = i == selected_tab_idx

            # Get rule count for indicator
            if i == 0:
                rule_count = len(config.always_deny)
            elif i == 1:
                rule_count = len(config.always_ask)
            else:
                rule_count = len(config.always_allow)

            prefix = f"{prompt_symbol} " if is_selected else "  "
            indicator = f" ({rule_count})" if rule_count > 0 else ""

            tab_text = f"{prefix}{tab_name}{indicator}  "
            tab_len = len(tab_text)

            # Wrap to next line if exceeds width
            if current_line_len + tab_len > term_width and current_line_len > 0:
                lines.append(("", "\n"))
                current_line_len = 0

            style = theme.selection_color if is_selected else ""
            lines.append((style, f"{prefix}{tab_name}"))
            if rule_count > 0:
                lines.append((theme.muted_text, f" ({rule_count})"))
            lines.append(("", "  "))
            current_line_len += tab_len

        lines.append(("", "\n\n"))

        # Rules list for selected tab
        if selected_tab_idx == 0:
            rules = config.always_deny
        elif selected_tab_idx == 1:
            rules = config.always_ask
        else:
            rules = config.always_allow

        if not rules:
            lines.append((theme.muted_text, "  (no rules)"))
        else:
            for i, rule in enumerate(rules):
                is_selected = i == selected_rule_idx
                prefix = f"{prompt_symbol} " if is_selected else "  "
                style = theme.selection_color if is_selected else ""

                # Format rule display
                rule_display = self._format_rule(rule)
                lines.append((style, f"{prefix}{rule_display}"))

                if i < len(rules) - 1:
                    lines.append(("", "\n"))

        return FormattedText(lines)

    @staticmethod
    def _format_rule(rule: ToolApprovalRule) -> str:
        """Format a single rule for display."""
        if rule.args:
            args_str = ", ".join(f"{k}={v}" for k, v in rule.args.items())
            return f"{rule.name}: {args_str}"
        else:
            return rule.name

    def _open_in_editor(self, config_file: Path) -> None:
        """Open config file in editor."""
        editor = settings.cli.editor
        try:
            subprocess.run([editor, str(config_file)], check=True)
        except subprocess.CalledProcessError as e:
            console.print_error(f"Editor exited with error: {e}")
            console.print("")
        except FileNotFoundError:
            console.print_error(
                f"Editor '{editor}' not found. Install it or set CLI__EDITOR in .env"
            )
            console.print("")
