"""Model handling for chat sessions."""

import sys

from prompt_toolkit.application import Application
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import FormattedTextControl

from src.cli.bootstrap.initializer import initializer
from src.cli.theme import console, theme
from src.core.config import AgentConfig, LLMConfig
from src.core.logging import get_logger
from src.core.settings import settings

logger = get_logger(__name__)


class ModelHandler:
    """Handles model operations like switching and selection."""

    def __init__(self, session):
        """Initialize with reference to CLI session."""
        self.session = session

    async def handle(self) -> None:
        """Show interactive selector to switch model for agent or its subagents."""
        try:
            current_agent_config = await initializer.load_agent_config(
                self.session.context.agent, self.session.context.working_dir
            )

            agents_to_show = [
                ("agent", self.session.context.agent, current_agent_config)
            ]

            if current_agent_config.subagents:
                agents_to_show.extend(
                    ("subagent", subagent.name, subagent)
                    for subagent in current_agent_config.subagents
                )

            selected_agent = await self._get_agent_selection(agents_to_show)
            if not selected_agent:
                return

            agent_type, agent_name, agent_config = selected_agent

            config_data = await initializer.load_llms_config(
                self.session.context.working_dir
            )
            models = config_data.llms

            if agent_type == "agent":
                current_model_name = self.session.context.model
            else:
                current_model_name = agent_config.llm.alias

            default_model_name = agent_config.llm.alias

            if len(models) == 1:
                console.print_error("No other models available")
                console.print("")
                return

            selected_model_name = await self._get_model_selection(
                models, current_model_name, default_model_name
            )

            if selected_model_name:
                if agent_type == "agent":
                    await initializer.update_agent_llm(
                        agent_name,
                        selected_model_name,
                        self.session.context.working_dir,
                    )

                    new_llm_config = next(
                        (m for m in models if m.alias == selected_model_name), None
                    )

                    self.session.update_context(
                        model=selected_model_name,
                        context_window=(
                            new_llm_config.context_window if new_llm_config else None
                        ),
                        input_cost_per_mtok=(
                            new_llm_config.input_cost_per_mtok
                            if new_llm_config
                            else None
                        ),
                        output_cost_per_mtok=(
                            new_llm_config.output_cost_per_mtok
                            if new_llm_config
                            else None
                        ),
                    )
                else:
                    await initializer.update_subagent_llm(
                        agent_name,
                        selected_model_name,
                        self.session.context.working_dir,
                    )
                    console.print_success(
                        f"Updated subagent '{agent_name}' to use model '{selected_model_name}'"
                    )
                    console.print("")

        except Exception as e:
            console.print_error(f"Error switching models: {e}")
            console.print("")
            logger.debug("Model switch error", exc_info=True)

    async def _get_agent_selection(
        self, agents: list[tuple[str, str, AgentConfig]]
    ) -> tuple[str, str, AgentConfig] | None:
        """Get agent selection from user (current agent + subagents).

        Args:
            agents: List of (agent_type, agent_name, agent_config) tuples

        Returns:
            Selected tuple or None if canceled
        """
        if not agents:
            return None

        current_index = 0

        text_control = FormattedTextControl(
            text=lambda: self._format_agent_list(agents, current_index),
            focusable=True,
            show_cursor=False,
        )

        kb = KeyBindings()

        @kb.add(Keys.Up)
        def _(event):
            nonlocal current_index
            current_index = (current_index - 1) % len(agents)

        @kb.add(Keys.Down)
        def _(event):
            nonlocal current_index
            current_index = (current_index + 1) % len(agents)

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
                if sys.stdout.isatty():
                    num_lines = len(agents)
                    for _i in range(num_lines):
                        sys.stdout.write("\033[F")
                        sys.stdout.write("\033[K")
                    sys.stdout.flush()
                return agents[current_index]

            console.print("")
            return None

        except (KeyboardInterrupt, EOFError):
            console.print("")
            return None

    async def _get_model_selection(
        self, models: list[LLMConfig], current_model: str, default_model: str
    ) -> str:
        """Get model selection from user using interactive list.

        Args:
            models: List of model configuration objects
            current_model: Currently active model name
            default_model: Default model name from config

        Returns:
            Selected model name or empty string if canceled
        """
        if not models:
            return ""

        current_index = 0

        # Create text control with formatted text
        text_control = FormattedTextControl(
            text=lambda: self._format_model_list(
                models, current_index, current_model, default_model
            ),
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
                if sys.stdout.isatty():
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

    def _format_agent_list(
        self, agents: list[tuple[str, str, AgentConfig]], selected_index: int
    ):
        """Format the agent list with highlighting.

        Args:
            agents: List of (agent_type, agent_name, agent_config) tuples
            selected_index: Index of currently selected agent

        Returns:
            FormattedText with styled lines
        """
        prompt_symbol = settings.cli.prompt_style.strip()
        lines = []
        for i, (agent_type, agent_name, agent_config) in enumerate(agents):
            # For main agent, use context model; for subagents, use config model
            if agent_type == "agent":
                model_name = self.session.context.model
            else:
                model_name = agent_config.llm.alias

            type_label = "Agent" if agent_type == "agent" else "Subagent"

            display_text = f"[{type_label}] {agent_name} ({model_name})"

            if i == selected_index:
                lines.append(
                    (f"{theme.selection_color}", f"{prompt_symbol} {display_text}")
                )
            else:
                lines.append(("", f"  {display_text}"))

            if i < len(agents) - 1:
                lines.append(("", "\n"))

        return FormattedText(lines)

    @staticmethod
    def _format_model_list(
        models: list[LLMConfig],
        selected_index: int,
        current_model: str,
        default_model: str,
    ):
        """Format the model list with highlighting.

        Args:
            models: List of model configuration objects
            selected_index: Index of currently selected model
            current_model: Currently active model name
            default_model: Default model name from config

        Returns:
            FormattedText with styled lines
        """
        prompt_symbol = settings.cli.prompt_style.strip()
        lines = []
        for i, model in enumerate(models):
            model_name = model.alias
            provider = model.provider.value

            # Build the base text
            base_text = f"{model_name} ({provider})"

            # Check for indicators
            is_current = model_name == current_model
            is_default = model_name == default_model

            if i == selected_index:
                # Selected item - highlight the whole line
                lines.append(
                    (f"{theme.selection_color}", f"{prompt_symbol} {base_text}")
                )
                # Add indicators on the same line with colors
                if is_current:
                    lines.append((f"{theme.info_color}", " [current]"))
                if is_default:
                    lines.append((f"{theme.accent_color}", " [default]"))
            else:
                # Non-selected item
                lines.append(("", f"  {base_text}"))
                # Add indicators with colors
                if is_current:
                    lines.append((f"{theme.info_color}", " [current]"))
                if is_default:
                    lines.append((f"{theme.accent_color}", " [default]"))

            if i < len(models) - 1:
                lines.append(("", "\n"))

        return FormattedText(lines)
