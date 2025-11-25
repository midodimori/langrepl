"""Prompt-toolkit session and input handling."""

import os
import time
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.filters import completion_is_selected
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.styles import Style

from src.cli.completers import CompleterRouter
from src.cli.core.context import Context
from src.cli.theme import theme
from src.core.config import ApprovalMode
from src.core.constants import CONFIG_HISTORY_FILE_NAME
from src.core.settings import settings
from src.utils.cost import calculate_context_percentage, format_cost, format_tokens
from src.utils.version import get_version


class InteractivePrompt:
    """Interactive prompt interface using prompt-toolkit."""

    def __init__(self, context: Context, commands: list[str], session=None):
        self.context = context
        self.commands = commands
        self.session = session
        history_file = Path(context.working_dir) / CONFIG_HISTORY_FILE_NAME
        history_file.parent.mkdir(parents=True, exist_ok=True)
        self.history = FileHistory(str(history_file))
        self.prompt_session: PromptSession[str]
        self.completer: CompleterRouter
        self.mode_change_callback = None
        self.bash_mode_toggle_callback = None
        self._last_ctrl_c_time: float | None = None
        self._ctrl_c_timeout = 0.5  # 500ms window for double-press detection
        self._show_quit_message = False
        self.hotkeys: dict[str, str] = {}
        self._setup_session()

    @staticmethod
    def _format_key_name(key) -> str:
        """Format key enum to human-readable string."""
        key_str = str(key)
        replacements = {
            "Keys.Control": "Ctrl+",
            "Keys.Back": "Shift+",
            "Keys.": "",
        }
        for old, new in replacements.items():
            key_str = key_str.replace(old, new)
        return key_str

    def _setup_session(self) -> None:
        """Set up the prompt session with all configurations."""
        # Create key bindings
        kb = self._create_key_bindings()

        # Create style
        style = self._create_style()

        # Create completer router for slash commands and @ references
        self.completer = CompleterRouter(
            commands=self.commands,
            working_dir=Path(self.context.working_dir),
            max_suggestions=settings.cli.max_autocomplete_suggestions,
        )

        # Create session
        self.prompt_session = PromptSession(
            history=self.history,
            auto_suggest=AutoSuggestFromHistory(),
            completer=self.completer,
            complete_style=CompleteStyle.COLUMN,
            key_bindings=kb,
            style=style,
            multiline=False,
            prompt_continuation=lambda width, line_number, is_soft_wrap: " "
            * len(settings.cli.prompt_style),
            wrap_lines=settings.cli.enable_word_wrap,
            mouse_support=False,
            complete_while_typing=True,
            complete_in_thread=False,
            placeholder=self._get_placeholder,
            bottom_toolbar=self._get_bottom_toolbar,
        )

    def _create_key_bindings(self) -> KeyBindings:
        """Create custom key bindings."""
        kb = KeyBindings()
        self.hotkeys.clear()

        @kb.add(Keys.ControlC)
        def _(event):
            """Ctrl-C: Clear input if text exists, or quit on double-press."""
            buffer = event.current_buffer
            current_time = time.time()

            # If there's text in the buffer, clear it
            if buffer.text.strip():
                buffer.delete_before_cursor(len(buffer.text))
                self._last_ctrl_c_time = None  # Reset timer after clearing
                self._show_quit_message = False
                return

            # If buffer is empty, check for double-press
            if self._last_ctrl_c_time is not None:
                time_since_last = current_time - self._last_ctrl_c_time
                if time_since_last < self._ctrl_c_timeout:
                    # Double-press detected within timeout, quit
                    raise KeyboardInterrupt()
                # Double-press timeout expired, reset
                self._last_ctrl_c_time = current_time
                self._show_quit_message = True
                self._schedule_hide_message(event.app)
            else:
                # First press on empty buffer
                self._last_ctrl_c_time = current_time
                self._show_quit_message = True
                self._schedule_hide_message(event.app)

        @kb.add(Keys.ControlJ)
        def _(event):
            """Ctrl-J: Insert newline for multiline input."""
            event.current_buffer.insert_text("\n")

        @kb.add(Keys.BackTab)
        def _(event):
            """Shift-Tab: Cycle approval mode."""
            if self.mode_change_callback:
                self.mode_change_callback()

        @kb.add(Keys.ControlB)
        def _(event):
            """Ctrl-B: Toggle bash mode."""
            if self.bash_mode_toggle_callback:
                self.bash_mode_toggle_callback()

        @kb.add(Keys.ControlK)
        def _(event):
            """Ctrl-K: Show keyboard shortcuts."""
            buffer = event.current_buffer
            buffer.text = "/hotkeys"
            buffer.validate_and_handle()

        @kb.add(Keys.Enter, filter=completion_is_selected)
        def _(event):
            """Enter when completion is selected: apply completion."""
            buffer = event.current_buffer
            if buffer.complete_state:
                current_completion = buffer.complete_state.current_completion
                buffer.apply_completion(current_completion)

                # For slash commands, submit immediately
                if buffer.text.lstrip().startswith("/"):
                    buffer.validate_and_handle()
                # For @ references, add space
                else:
                    buffer.insert_text(" ")

        @kb.add(Keys.Tab)
        def _(event):
            """Tab: apply first completion immediately."""
            buffer = event.current_buffer

            # If completion is already showing and selected, apply it
            if buffer.complete_state and buffer.complete_state.current_completion:
                current_completion = buffer.complete_state.current_completion
                buffer.apply_completion(current_completion)

                # For @ references, add space
                if not buffer.text.lstrip().startswith("/"):
                    buffer.insert_text(" ")
            else:
                # Start completion with first item selected
                buffer.start_completion(select_first=True)
                # Immediately apply the first completion
                if buffer.complete_state and buffer.complete_state.current_completion:
                    current_completion = buffer.complete_state.current_completion
                    buffer.apply_completion(current_completion)

                    # For @ references, add space
                    if not buffer.text.lstrip().startswith("/"):
                        buffer.insert_text(" ")

        # Register hotkey descriptions
        self.hotkeys = {
            self._format_key_name(Keys.ControlC): "Clear input (press twice to quit)",
            self._format_key_name(Keys.ControlJ): "Insert newline for multiline input",
            self._format_key_name(Keys.BackTab): "Cycle approval mode",
            self._format_key_name(Keys.ControlB): "Toggle bash mode",
            self._format_key_name(Keys.ControlK): "Show keyboard shortcuts",
            "Tab": "Apply first completion",
            "Enter": "Apply selected completion or submit",
        }

        return kb

    def set_mode_change_callback(self, callback):
        """Set callback for mode change events."""
        self.mode_change_callback = callback

    def set_bash_mode_toggle_callback(self, callback):
        """Set callback for bash mode toggle events."""
        self.bash_mode_toggle_callback = callback

    def _get_placeholder(self) -> HTML:
        """Generate placeholder text with agent name and usage info."""
        agent_name = f"{self.context.agent}:{self.context.model}"

        # Build token/cost info if available
        usage_info = ""
        ctx = self.context

        # Show tokens if context window is available and we have token data
        if (
            ctx.context_window is not None
            and ctx.current_input_tokens is not None
            and ctx.current_output_tokens is not None
            and ctx.current_input_tokens > 0
        ):
            total_tokens = ctx.current_input_tokens + ctx.current_output_tokens
            tokens_formatted = format_tokens(total_tokens)
            window_formatted = format_tokens(ctx.context_window)
            percentage = calculate_context_percentage(total_tokens, ctx.context_window)
            usage_info = (
                f"  [{tokens_formatted}/{window_formatted} tokens ({percentage:.0f}%)"
            )

            # Add cost if pricing fields are available
            if (
                ctx.input_cost_per_mtok is not None
                and ctx.output_cost_per_mtok is not None
                and ctx.total_cost is not None
            ):
                cost_formatted = format_cost(ctx.total_cost)
                usage_info += f" | {cost_formatted}"

            usage_info += "]"

        return HTML(f"<placeholder>{agent_name}{usage_info}</placeholder>")

    def _get_bottom_toolbar(self) -> HTML:
        """Generate bottom toolbar text with version, working directory and approval mode."""
        if self._show_quit_message:
            return HTML("<muted> Ctrl+C again to quit</muted>")

        mode_name = self.context.approval_mode.value
        terminal_width = os.get_terminal_size().columns if os.isatty(1) else 80
        version = get_version()
        left_content = f" v{version} | {self.context.working_dir}"

        # Build right content with bash mode if active
        right_parts = (
            ["bash-mode", mode_name] if self.context.bash_mode else [mode_name]
        )
        right_content = " | ".join(right_parts)

        # Calculate padding
        padding = " " * max(
            0, terminal_width - len(left_content) - len(right_content) - 1
        )

        # Build styled output
        if self.context.bash_mode:
            styled_right = f"<toolbar.bash>bash-mode</toolbar.bash><muted> | </muted><toolbar.mode>{mode_name}</toolbar.mode>"
        else:
            styled_right = f"<toolbar.mode>{mode_name}</toolbar.mode>"

        return HTML(
            f"<muted>{left_content}{padding}</muted>{styled_right}<muted> </muted>"
        )

    def _schedule_hide_message(self, app):
        """Schedule hiding the quit message after timeout."""

        def hide():
            self._show_quit_message = False
            self._last_ctrl_c_time = None
            app.invalidate()

        app.loop.call_later(self._ctrl_c_timeout, hide)

    def _get_prompt_color(self) -> str:
        """Get prompt color based on approval mode and bash mode."""
        if self.context.bash_mode:
            return theme.danger_color
        mode_colors = {
            ApprovalMode.SEMI_ACTIVE: theme.approval_semi_active,
            ApprovalMode.ACTIVE: theme.approval_active,
            ApprovalMode.AGGRESSIVE: theme.approval_aggressive,
        }
        return mode_colors[self.context.approval_mode]

    def refresh_style(self) -> None:
        """Refresh the prompt style after approval mode change."""
        if self.prompt_session:
            # Update the session style
            self.prompt_session.style = self._create_style()

    def _create_style(self) -> Style:
        """Create prompt style based on theme and approval mode."""
        # Get prompt color based on approval mode
        prompt_color = self._get_prompt_color()

        return Style.from_dict(
            {
                # Prompt styling - dynamic based on approval mode
                "prompt": f"{prompt_color} bold",
                "prompt.muted": f"{prompt_color} nobold",
                "prompt.arg": f"{theme.accent_color}",
                # Input styling
                "": f"{theme.primary_text}",
                "text": f"{theme.primary_text}",
                # Completion styling
                "completion-menu.completion": f"{theme.primary_text} bg:{theme.background_light}",
                "completion-menu.completion.current": f"{theme.background} bg:{theme.prompt_color}",
                "completion-menu.meta.completion": f"{theme.muted_text} bg:{theme.background_light}",
                "completion-menu.meta.completion.current": f"{theme.primary_text} bg:{theme.prompt_color}",
                # Thread completion styling
                "thread-completion": f"{theme.accent_color} bg:{theme.background_light}",
                # File/directory completion styling
                "file-completion": f"{theme.primary_text} bg:{theme.background_light}",
                "dir-completion": f"{theme.info_color} bg:{theme.background_light}",
                # Auto-suggestion styling
                "auto-suggestion": f"{theme.muted_text} italic",
                # Validation styling
                "validation-toolbar": f"{theme.error_color} bg:{theme.background_light}",
                # Selection styling
                "selected": f"bg:{theme.selection_color}",
                # Search styling
                "search": f"{theme.accent_color} bg:{theme.background_light}",
                "search.current": f"{theme.background} bg:{theme.warning_color}",
                # Placeholder styling
                "placeholder": f"{theme.muted_text} italic",
                # Muted text styling
                "muted": f"{theme.muted_text}",
                # Bottom toolbar styling - override default reverse
                "bottom-toolbar": f"noreverse {theme.muted_text}",
                "bottom-toolbar.text": f"noreverse {theme.muted_text}",
                # Toolbar mode styling - dynamic based on approval mode
                "toolbar.mode": f"noreverse {prompt_color}",
                # Toolbar bash mode styling - danger (pink)
                "toolbar.bash": f"noreverse {theme.danger_color}",
            }
        )

    async def get_input(self) -> tuple[str, bool]:
        """Get user input asynchronously."""
        try:
            prompt_text = [
                ("class:prompt", settings.cli.prompt_style),
            ]

            default_text = ""
            if self.session and self.session.prefilled_text:
                default_text = self.session.prefilled_text
                self.session.prefilled_text = None

            result = await self.prompt_session.prompt_async(prompt_text, default=default_text)  # type: ignore
            print()

            content = result.strip()

            is_command = False
            if content.startswith("/"):
                # If it's a known command, treat as command
                first_word = content.split()[0] if content.split() else content
                if first_word in self.commands:
                    is_command = True
                # If it has only one "/" at the start and no path separators after,
                # treat as command (e.g., "/help", "/exit")
                elif "/" not in content[1:]:
                    is_command = True
                # Otherwise it's likely a file path, treat as regular content

            return content, is_command

        except (KeyboardInterrupt, EOFError):
            raise
