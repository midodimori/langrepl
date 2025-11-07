"""Prompt-toolkit session and input handling."""

import asyncio
import os
import re
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


class InteractivePrompt:
    """Interactive prompt interface using prompt-toolkit."""

    def __init__(self, context: Context, commands: list[str], session=None):
        """
        Initialize the interactive prompt state and prepare a prompt-toolkit session.
        
        Creates a persistent history file in the context's working directory, initializes internal attributes used for completion, keybinding and Ctrl+C handling, sets a 500ms window for double-Ctrl+C detection, and calls _setup_session to configure the PromptSession and related components.
        
        Parameters:
            context (Context): Execution context containing configuration such as working_dir, agent/model names, and token/cost data used to build prompts and toolbars.
            commands (list[str]): List of available command strings used to initialize the completer.
            session: Optional external session or state object to associate with this prompt instance; stored on the instance if provided.
        """
        self.context = context
        self.commands = commands
        self.session = session
        history_file = Path(context.working_dir) / CONFIG_HISTORY_FILE_NAME
        history_file.parent.mkdir(parents=True, exist_ok=True)
        self.history = FileHistory(str(history_file))
        self.prompt_session: PromptSession[str]
        self.completer: CompleterRouter
        self.mode_change_callback = None
        self._last_ctrl_c_time: float | None = None
        self._ctrl_c_timeout = 0.5  # 500ms window for double-press detection
        self._show_quit_message = False
        self._setup_session()

    def _setup_session(self) -> None:
        """
        Initialize interactive prompt components and create the PromptSession used for input.
        
        This configures key bindings and visual style, constructs the completer for slash-commands and
        `@` references, and instantiates `self.prompt_session` with history, autosuggestion, completion
        behavior, placeholder and bottom-toolbar providers, and other session options.
        """
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
        """
        Create and return the prompt key bindings used by the interactive session.
        
        Bindings:
        - Ctrl+C: If the current buffer contains text, clear it; if empty, show a one-time "press again to quit" message and, if pressed again within the configured timeout, raise KeyboardInterrupt to quit.
        - Ctrl+J: Insert a newline into the current buffer (supports multiline input).
        - Shift+Tab (BackTab): Invoke the stored mode change callback, if any.
        - Enter (when a completion is selected): Apply the selected completion; if the resulting text is a slash command (starts with "/"), submit it immediately; otherwise insert a space and, if the text ends with an @-reference, resolve it and store the mapping on the session (if available).
        - Tab: If a completion is already selected, apply it; otherwise start completion selecting the first item and apply it; for non-slash inputs, insert a space and resolve/store @-reference mappings similarly.
        
        Returns:
            KeyBindings: A configured prompt_toolkit KeyBindings instance with the above behaviors.
        """
        kb = KeyBindings()

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

        @kb.add(Keys.Enter, filter=completion_is_selected)
        def _(event):
            """
            Apply the currently selected completion from the prompt buffer and handle post-completion side effects.
            
            Parameters:
            	event: The key binding event containing the current prompt buffer.
            
            Behavior:
            - If a completion is active, apply it to the buffer.
            - If the resulting buffer text (left-stripped) begins with "/", submit the buffer immediately.
            - Otherwise, insert a single space after the applied completion. If the buffer now ends with an `@`-style reference matching the pattern `@:<word>:<non-space>`, resolve that reference via the completer and, if a session object exists, store the mapping in `self.session.prefilled_reference_mapping`.
            """
            buffer = event.current_buffer
            if buffer.complete_state:
                current_completion = buffer.complete_state.current_completion
                buffer.apply_completion(current_completion)

                # For slash commands, submit immediately
                if buffer.text.lstrip().startswith("/"):
                    buffer.validate_and_handle()
                # For @ references, add space and save mapping
                else:
                    buffer.insert_text(" ")
                    match = re.search(r"(@:\w+:\S+)\s*$", buffer.text)
                    if match:
                        ref = match.group(1)
                        resolved = self.completer.resolve_refs(ref)
                        if self.session:
                            self.session.prefilled_reference_mapping[ref] = resolved

        @kb.add(Keys.Tab)
        def _(event):
            """
            Apply the first completion for the current buffer when Tab is pressed.
            
            If a completion is already selected, it is applied immediately; otherwise completion is started with the first item selected and then applied. If the resulting input does not start with "/", a trailing space is inserted and any trailing `@:name:ref` reference is resolved and stored in self.session.prefilled_reference_mapping when a session exists.
            
            Parameters:
                event: The prompt_toolkit key binding event whose current_buffer will be completed.
            """
            buffer = event.current_buffer

            # If completion is already showing and selected, apply it
            if buffer.complete_state and buffer.complete_state.current_completion:
                current_completion = buffer.complete_state.current_completion
                buffer.apply_completion(current_completion)

                # For @ references, add space and save mapping
                if not buffer.text.lstrip().startswith("/"):
                    buffer.insert_text(" ")
                    match = re.search(r"(@:\w+:\S+)\s*$", buffer.text)
                    if match:
                        ref = match.group(1)
                        resolved = self.completer.resolve_refs(ref)
                        if self.session:
                            self.session.prefilled_reference_mapping[ref] = resolved
            else:
                # Start completion with first item selected
                buffer.start_completion(select_first=True)
                # Immediately apply the first completion
                if buffer.complete_state and buffer.complete_state.current_completion:
                    current_completion = buffer.complete_state.current_completion
                    buffer.apply_completion(current_completion)

                    # For @ references, add space and save mapping
                    if not buffer.text.lstrip().startswith("/"):
                        buffer.insert_text(" ")
                        match = re.search(r"(@:\w+:\S+)\s*$", buffer.text)
                        if match:
                            ref = match.group(1)
                            resolved = self.completer.resolve_refs(ref)
                            if self.session:
                                self.session.prefilled_reference_mapping[ref] = resolved

        return kb

    def set_mode_change_callback(self, callback):
        """Set callback for mode change events."""
        self.mode_change_callback = callback

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
        """Generate bottom toolbar text with working directory and approval mode."""
        if self._show_quit_message:
            return HTML(f"<muted> Ctrl+C again to quit</muted>")

        mode_name = self.context.approval_mode.value
        working_dir = self.context.working_dir

        try:
            terminal_width = os.get_terminal_size().columns
        except OSError:
            terminal_width = 80

        # Calculate spacing to right-align the mode
        left_content = f" {working_dir}"
        right_content = f"{mode_name} | Shift+Tab "
        spaces_needed = max(0, terminal_width - len(left_content) - len(right_content))
        padding = " " * spaces_needed

        return HTML(
            f"<muted>{left_content}{padding}</muted><toolbar.mode>{mode_name}</toolbar.mode><muted> | Shift+Tab </muted>"
        )

    def _schedule_hide_message(self, app):
        """Schedule hiding the quit message after timeout."""

        async def hide_after_timeout():
            await asyncio.sleep(self._ctrl_c_timeout)
            self._show_quit_message = False
            self._last_ctrl_c_time = None
            app.invalidate()

        asyncio.create_task(hide_after_timeout())

    def _get_prompt_color(self) -> str:
        """Get prompt color based on approval mode."""
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
        """
        Build a prompt_toolkit Style configured from the current theme and approval mode.
        
        Returns:
            style (Style): A Style object mapping UI tokens to color and attribute strings; includes dynamic entries that reflect the current approval mode and theme.
        """
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
            }
        )

    async def get_input(self) -> tuple[str, bool]:
        """
        Read a line of input from the prompt session and return the trimmed content and whether it starts with a slash.
        
        If a prefilled value is present on the session, it will be consumed as the prompt's default text.
        
        Returns:
            tuple: (content, is_command) where `content` is the trimmed input string and `is_command` is `True` if `content` starts with '/', `False` otherwise.
        
        Raises:
            KeyboardInterrupt: If the user cancels input (e.g., double Ctrl+C).
            EOFError: If end-of-file is encountered while reading input.
        """
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
            return content, content.startswith("/")

        except (KeyboardInterrupt, EOFError):
            raise