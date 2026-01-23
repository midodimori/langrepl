"""Model handling for chat sessions."""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

from prompt_toolkit.application import Application
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl

from langrepl.cli.bootstrap.initializer import initializer
from langrepl.cli.theme import console, theme
from langrepl.cli.ui.shared import (
    create_bottom_toolbar,
    create_instruction,
    create_prompt_style,
)
from langrepl.core.logging import get_logger
from langrepl.core.settings import settings

if TYPE_CHECKING:
    from langrepl.configs import AgentConfig, LLMConfig, SubAgentConfig

logger = get_logger(__name__)


class ModelHandler:
    """Handles model operations like switching and selection."""

    def __init__(self, session) -> None:
        """Initialize with reference to CLI session."""
        self.session = session

    async def handle(self) -> None:
        """Show interactive selector to switch model for agent or its subagents."""
        try:
            current_agent_config = await initializer.load_agent_config(
                self.session.context.agent, self.session.context.working_dir
            )

            agents_to_show: list[tuple[str, str, AgentConfig | SubAgentConfig]] = [
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
                    logger.info(f"Switched to Model: {selected_model_name}")
                else:
                    await initializer.update_subagent_llm(
                        agent_name,
                        selected_model_name,
                        self.session.context.working_dir,
                    )
                    logger.info(
                        f"Subagent '{agent_name}' switched to Model: {selected_model_name}"
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
        self, agents: list[tuple[str, str, AgentConfig | SubAgentConfig]]
    ) -> tuple[str, str, AgentConfig | SubAgentConfig] | None:
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

        context = self.session.context
        app: Application = Application(
            layout=Layout(
                HSplit(
                    [
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

        selected_agent: tuple[str, str, AgentConfig | SubAgentConfig] | None = None

        try:
            await app.run_async()

            if selected[0]:
                selected_agent = agents[current_index]

        except (KeyboardInterrupt, EOFError):
            pass

        return selected_agent

    async def _get_model_selection(
        self, models: list[LLMConfig], current_model: str, default_model: str
    ) -> str:
        """Get model selection from user using tabbed provider interface.

        Args:
            models: List of model configuration objects
            current_model: Currently active model name
            default_model: Default model name from config

        Returns:
            Selected model name or empty string if canceled
        """
        if not models:
            return ""

        # Group models by provider
        providers = self._group_models_by_provider(models)
        provider_names = list(providers.keys())
        current_provider_idx = 0
        current_model_idx = 0

        # Find initial provider/model based on current model
        for pi, pname in enumerate(provider_names):
            for mi, m in enumerate(providers[pname]):
                if m.alias == current_model:
                    current_provider_idx, current_model_idx = pi, mi
                    break

        text_control = FormattedTextControl(
            text=lambda: self._format_tabbed_model_list(
                providers,
                provider_names,
                current_provider_idx,
                current_model_idx,
                current_model,
                default_model,
            ),
            focusable=True,
            show_cursor=False,
        )

        kb = KeyBindings()

        @kb.add(Keys.Tab)
        def _(event):
            nonlocal current_provider_idx, current_model_idx
            current_provider_idx = (current_provider_idx + 1) % len(provider_names)
            current_model_idx = 0

        @kb.add(Keys.BackTab)
        def _(event):
            nonlocal current_provider_idx, current_model_idx
            current_provider_idx = (current_provider_idx - 1) % len(provider_names)
            current_model_idx = 0

        @kb.add(Keys.Up)
        def _(event):
            nonlocal current_model_idx
            provider = provider_names[current_provider_idx]
            current_model_idx = (current_model_idx - 1) % len(providers[provider])

        @kb.add(Keys.Down)
        def _(event):
            nonlocal current_model_idx
            provider = provider_names[current_provider_idx]
            current_model_idx = (current_model_idx + 1) % len(providers[provider])

        selected = [False]

        @kb.add(Keys.Enter)
        def _(event):
            selected[0] = True
            event.app.exit()

        @kb.add(Keys.ControlC)
        def _(event):
            event.app.exit()

        context = self.session.context
        app: Application = Application(
            layout=Layout(
                HSplit(
                    [
                        *create_instruction("←: Shift+Tab, →: Tab"),
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

        selected_model = ""

        try:
            await app.run_async()

            if selected[0]:
                provider = provider_names[current_provider_idx]
                selected_model = providers[provider][current_model_idx].alias

        except (KeyboardInterrupt, EOFError):
            pass

        return selected_model

    @staticmethod
    def _group_models_by_provider(
        models: list[LLMConfig],
    ) -> dict[str, list[LLMConfig]]:
        """Group models by their provider."""
        grouped: dict[str, list[LLMConfig]] = {}
        for m in models:
            key = m.provider.value
            grouped.setdefault(key, []).append(m)
        return grouped

    def _format_tabbed_model_list(
        self,
        providers: dict[str, list[LLMConfig]],
        provider_names: list[str],
        selected_provider_idx: int,
        selected_model_idx: int,
        current_model: str,
        default_model: str,
    ) -> FormattedText:
        """Format tabbed model list with provider tabs and model entries."""
        prompt_symbol = settings.cli.prompt_style.strip()
        term_width = shutil.get_terminal_size().columns

        # Build provider->indicator map
        current_provider = default_provider = None
        for pname, pmodels in providers.items():
            if any(m.alias == current_model for m in pmodels):
                current_provider = pname
            if any(m.alias == default_model for m in pmodels):
                default_provider = pname

        # Tab bar with wrapping
        lines: list[tuple[str, str]] = []
        current_line_len = 0

        for i, pname in enumerate(provider_names):
            is_selected = i == selected_provider_idx
            prefix = f"{prompt_symbol} " if is_selected else "  "
            indicator = ""
            if pname == current_provider:
                indicator = " ●"
            elif pname == default_provider:
                indicator = " ○"

            tab_text = f"{prefix}{pname}{indicator}  "
            tab_len = len(tab_text)

            # Wrap to next line if exceeds width
            if current_line_len + tab_len > term_width and current_line_len > 0:
                lines.append(("", "\n"))
                current_line_len = 0

            style = theme.selection_color if is_selected else ""
            lines.append((style, f"{prefix}{pname}"))
            if pname == current_provider:
                lines.append((theme.accent_color, " ●"))
            elif pname == default_provider:
                lines.append((theme.info_color, " ○"))
            lines.append(("", "  "))
            current_line_len += tab_len

        lines.append(("", "\n\n"))

        # Model list for selected provider
        active_provider = provider_names[selected_provider_idx]
        for i, model in enumerate(providers[active_provider]):
            is_selected = i == selected_model_idx
            is_current = model.alias == current_model
            is_default = model.alias == default_model

            prefix = f"{prompt_symbol} " if is_selected else "  "
            style = theme.selection_color if is_selected else ""
            lines.append((style, f"{prefix}{model.alias}"))
            if is_current:
                lines.append((theme.accent_color, " [current]"))
            if is_default:
                lines.append((theme.info_color, " [default]"))
            lines.append(("", "\n"))

        return FormattedText(lines)

    def _format_agent_list(
        self,
        agents: list[tuple[str, str, AgentConfig | SubAgentConfig]],
        selected_index: int,
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
