"""HIL interrupt management for LangGraph execution."""

import sys

from langgraph.types import Interrupt
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.styles import Style

from src.cli.theme import console, theme
from src.core.logging import get_logger
from src.core.settings import settings
from src.middleware.approval import InterruptPayload

logger = get_logger(__name__)


class InterruptHandler:
    """Handles LangGraph interrupts and collects user input for resume."""

    async def handle(
        self, interrupt_data: list[Interrupt]
    ) -> str | dict[str, str] | None:
        """
        Handle a LangGraph interrupts and collect user input.

        Args:
            interrupt_data: List of Interrupt objects from LangGraph

        Returns:
            Resume value to pass back to LangGraph:
            - For single interrupt: returns the resume value directly
            - For multiple interrupts: returns dict mapping interrupt IDs to resume values
        """
        try:
            if not interrupt_data:
                logger.warning("Empty interrupt data received")
                return None

            # Handle single interrupt - return value directly
            if len(interrupt_data) == 1:
                return await self._get_choice(interrupt_data[0])

            # Handle multiple interrupts - return dict mapping IDs to values
            resume_dict = {}
            for interrupt in interrupt_data:
                choice = await self._get_choice(interrupt)
                if choice is not None:
                    resume_dict[interrupt.id] = choice

            return resume_dict if resume_dict else None

        except Exception as e:
            console.print_error(f"Error handling interrupt: {e}")
            console.print("")
            return None

    @staticmethod
    async def _get_choice(interrupt: Interrupt) -> str | None:
        """Choice selector with tab completion and Enter key support."""
        value: InterruptPayload = interrupt.value
        question = value.question
        options = value.options

        # Measure actual rendered lines by capturing output
        with console.capture() as capture:
            console.print(f"[accent]{question}[/accent]")
        rendered_text = capture.get()
        # Count actual newlines in the rendered output (not stripping)
        # This gives us the exact number of line breaks
        lines_to_clear = rendered_text.count("\n")

        # Now print for real
        console.print(f"[accent]{question}[/accent]")
        completer = WordCompleter(options, ignore_case=True)

        # Create style
        style = Style.from_dict(
            {
                "prompt": f"{theme.prompt_color} bold",
                "completion-menu.completion": f"{theme.primary_text} bg:{theme.background_light}",
                "completion-menu.completion.current": f"{theme.background} bg:{theme.prompt_color} bold",
            }
        )

        session: PromptSession[str] = PromptSession(
            completer=completer,
            complete_style=CompleteStyle.COLUMN,
            complete_while_typing=False,
            style=style,
        )

        while True:
            try:

                def pre_run():
                    session.default_buffer.start_completion(select_first=False)

                result = await session.prompt_async(
                    [
                        ("class:prompt", settings.cli.prompt_style),
                    ],
                    pre_run=pre_run,
                )

                if not result.strip():
                    console.print_error("Please make a choice")
                    lines_to_clear += 2  # prompt + warning
                    continue

                # Validate the result
                result_lower = result.strip().lower()

                # Check if matches option name (case-insensitive)
                matched_option = None
                for option in options:
                    if option.lower() == result_lower:
                        matched_option = option
                        break

                if matched_option:
                    # Clear all interrupt-related lines
                    for _ in range(lines_to_clear + 1):  # +1 for the final prompt
                        sys.stdout.write("\033[F")
                        sys.stdout.write("\033[K")
                    sys.stdout.flush()
                    return matched_option

                # Check partial matches
                matches = [o for o in options if o.lower().startswith(result_lower)]
                if len(matches) == 1:
                    # Clear all interrupt-related lines
                    for _ in range(lines_to_clear + 1):  # +1 for the final prompt
                        sys.stdout.write("\033[F")
                        sys.stdout.write("\033[K")
                    sys.stdout.flush()
                    return matches[0]
                elif len(matches) > 1:
                    console.print_error(
                        f"Ambiguous choice. Options: {', '.join(matches)}"
                    )
                    lines_to_clear += 2  # prompt + warning
                    continue

                console.print_error(f"Invalid choice '{result}'. Please try again.")
                lines_to_clear += 2  # prompt + warning

            except KeyboardInterrupt:
                # Clear all interrupt-related lines including the current prompt
                for _ in range(lines_to_clear + 1):  # +1 for current prompt
                    sys.stdout.write("\033[F")
                    sys.stdout.write("\033[K")
                sys.stdout.flush()
                return ""
            except EOFError:
                # Clear all interrupt-related lines including the current prompt
                for _ in range(lines_to_clear + 1):  # +1 for current prompt
                    sys.stdout.write("\033[F")
                    sys.stdout.write("\033[K")
                sys.stdout.flush()
                return ""
