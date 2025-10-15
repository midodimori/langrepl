"""Model handling for chat sessions."""

import sys

from prompt_toolkit.application import Application
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import FormattedTextControl

from src.cli.initializer import initializer
from src.cli.theme import console, theme
from src.core.config import LLMConfig
from src.core.logging import get_logger
from src.core.settings import settings

logger = get_logger(__name__)


class ModelHandler:
    """Handles model operations like switching and selection."""

    def __init__(self, session):
        """Initialize with reference to CLI session."""
        self.session = session

    async def handle(self) -> None:
        """Show interactive model selector and switch to selected model."""
        try:
            config_data = await initializer.load_llms_config(
                self.session.context.working_dir
            )
            models = config_data.llms

            # Filter out current model from the list
            current_model_name = self.session.context.model
            available_models = [
                model for model in models if model.alias != current_model_name
            ]

            if not available_models:
                console.print_error("No other models available")
                console.print("")
                return

            # Show interactive model selector
            selected_model_name = await self._get_model_selection(available_models)

            if selected_model_name:
                # Update the config file
                await initializer.update_agent_llm(
                    self.session.context.agent,
                    selected_model_name,
                    self.session.context.working_dir,
                )

                # Load new model's config to get pricing and context window
                new_llm_config = next(
                    (m for m in models if m.alias == selected_model_name), None
                )

                # Switch to the selected model with new pricing config
                self.session.update_context(
                    model=selected_model_name,
                    context_window=(
                        new_llm_config.context_window if new_llm_config else None
                    ),
                    input_cost_per_mtok=(
                        new_llm_config.input_cost_per_mtok if new_llm_config else None
                    ),
                    output_cost_per_mtok=(
                        new_llm_config.output_cost_per_mtok if new_llm_config else None
                    ),
                )

        except Exception as e:
            console.print_error(f"Error switching models: {e}")
            logger.debug("Model switch error", exc_info=True)

    async def _get_model_selection(self, models: list[LLMConfig]) -> str:
        """Get model selection from user using interactive list.

        Args:
            models: List of model configuration objects

        Returns:
            Selected model name or empty string if canceled
        """
        if not models:
            return ""

        current_index = 0

        # Create text control with formatted text
        text_control = FormattedTextControl(
            text=lambda: self._format_model_list(models, current_index),
            focusable=True,
            show_cursor=False,
        )

        # Create key bindings
        kb = KeyBindings()

        @kb.add(Keys.Up)
        def _(event):
            nonlocal current_index
            current_index = (current_index - 1) % len(models)

        @kb.add(Keys.Down)
        def _(event):
            nonlocal current_index
            current_index = (current_index + 1) % len(models)

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

            if selected[0]:
                # Clear the model list from screen
                num_lines = len(models)
                for _i in range(num_lines):
                    sys.stdout.write("\033[F")
                    sys.stdout.write("\033[K")
                sys.stdout.flush()
                model = models[current_index]
                return model.alias

            console.print("")
            return ""

        except (KeyboardInterrupt, EOFError):
            console.print("")
            return ""

    @staticmethod
    def _format_model_list(models: list[LLMConfig], selected_index: int):
        """Format the model list with highlighting.

        Args:
            models: List of model configuration objects
            selected_index: Index of currently selected model

        Returns:
            FormattedText with styled lines
        """
        prompt_symbol = settings.cli.prompt_style.strip()
        lines = []
        for i, model in enumerate(models):
            model_name = model.alias
            provider = model.provider.value

            display_text = f"{model_name} ({provider})"

            if i == selected_index:
                # Use direct color code for selected line
                lines.append(
                    (f"{theme.selection_color}", f"{prompt_symbol} {display_text}")
                )
            else:
                lines.append(("", f"  {display_text}"))

            if i < len(models) - 1:
                lines.append(("", "\n"))

        return FormattedText(lines)
