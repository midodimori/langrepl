"""Shared UI functions for consistent styling across prompt sessions."""

import html
import os

from prompt_toolkit.formatted_text import HTML, FormattedText
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.styles import Style

from src.cli.theme import theme
from src.core.config import ApprovalMode
from src.utils.version import get_version


def get_prompt_color(context, *, bash_mode: bool = False) -> str:
    """Get prompt color based on approval mode and bash mode."""
    if bash_mode:
        return theme.danger_color
    mode_colors = {
        ApprovalMode.SEMI_ACTIVE: theme.approval_semi_active,
        ApprovalMode.ACTIVE: theme.approval_active,
        ApprovalMode.AGGRESSIVE: theme.approval_aggressive,
    }
    return mode_colors[context.approval_mode]


def create_prompt_style(context, *, bash_mode: bool = False) -> Style:
    """Create prompt style based on theme and approval mode."""
    prompt_color = get_prompt_color(context, bash_mode=bash_mode)

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


def create_bottom_toolbar(
    context,
    working_dir: str,
    *,
    bash_mode: bool = False,
):
    """Create bottom toolbar with version, directory, and mode info."""
    terminal_width = os.get_terminal_size().columns if os.isatty(1) else 80
    version = get_version()
    working_dir_str = str(working_dir)

    # Left side: version + directory
    escaped_working_dir = html.escape(working_dir_str)
    left_text = f" v{version} | {working_dir_str}"
    left_content = f" v{version} | {escaped_working_dir}"

    # Right side: mode info
    mode_name = context.approval_mode.value

    right_parts = ["bash-mode", mode_name] if bash_mode else [mode_name]
    right_content = " | ".join(right_parts)

    # Calculate padding
    padding = " " * max(0, terminal_width - len(left_text) - len(right_content) - 1)

    # Build styled output
    if bash_mode:
        styled_right = f"<toolbar.bash>bash-mode</toolbar.bash><muted> | </muted><toolbar.mode>{mode_name}</toolbar.mode>"
    else:
        styled_right = f"<toolbar.mode>{mode_name}</toolbar.mode>"

    return HTML(f"<muted>{left_content}{padding}</muted>{styled_right}<muted> </muted>")


def create_instruction(
    message: str,
    *,
    spacer: bool = True,
) -> list[Window]:
    """Create instruction window with optional spacer for interactive lists."""
    windows = [
        Window(
            height=1,
            content=FormattedTextControl(
                lambda: FormattedText([("class:muted", message)])
            ),
            dont_extend_height=True,
        )
    ]
    if spacer:
        windows.append(Window(height=1, char=" "))
    return windows
