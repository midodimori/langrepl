"""Agent handling for chat sessions."""

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
from src.core.config import AgentConfig
from src.core.logging import get_logger
from src.core.settings import settings

logger = get_logger(__name__)


class AgentHandler:
    """Handles agent operations like switching and selection."""

    def __init__(self, session):
        """Initialize with reference to CLI session."""
        self.session = session

    async def handle(self) -> None:
        """Show interactive agent selector and switch to selected agent."""
        try:
            config_data = await initializer.load_agents_config(
                self.session.context.working_dir
            )
            agents = config_data.agents

            # Filter out current agent from the list
            current_agent_name = self.session.context.agent
            available_agents = [
                agent for agent in agents if agent.name != current_agent_name
            ]

            if not available_agents:
                console.print_error("No other agents available")
                console.print("")
                return

            # Show interactive agent selector
            selected_agent_name = await self._get_agent_selection(available_agents)

            if selected_agent_name:
                # Load the selected agent's config to get its model
                selected_agent_config = await initializer.load_agent_config(
                    selected_agent_name, self.session.context.working_dir
                )

                # Update context with both agent and its configured model
                self.session.update_context(
                    agent=selected_agent_name,
                    model=selected_agent_config.llm.alias,
                )

                # Mark this agent as the new default
                await initializer.update_default_agent(
                    selected_agent_name, self.session.context.working_dir
                )

        except Exception as e:
            console.print_error(f"Error switching agents: {e}")
            console.print("")
            logger.debug("Agent switch error", exc_info=True)

    async def _get_agent_selection(self, agents: list[AgentConfig]) -> str:
        """Get agent selection from user using interactive list.

        Args:
            agents: List of agent configuration objects

        Returns:
            Selected agent name or empty string if canceled
        """
        if not agents:
            return ""

        current_index = 0

        # Create text control with formatted text
        text_control = FormattedTextControl(
            text=lambda: self._format_agent_list(agents, current_index),
            focusable=True,
            show_cursor=False,
        )

        # Create key bindings
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

        # Create application
        app: Application = Application(
            layout=Layout(Window(content=text_control)),
            key_bindings=kb,
            full_screen=False,
        )

        try:
            await app.run_async()

            if selected[0]:
                # Clear the agent list from screen
                num_lines = len(agents)
                for _i in range(num_lines):
                    sys.stdout.write("\033[F")
                    sys.stdout.write("\033[K")
                sys.stdout.flush()
                agent = agents[current_index]
                return agent.name

            console.print("")
            return ""

        except (KeyboardInterrupt, EOFError):
            console.print("")
            return ""

    @staticmethod
    def _format_agent_list(agents: list[AgentConfig], selected_index: int):
        """Format the agent list with highlighting.

        Args:
            agents: List of agent configuration objects
            selected_index: Index of currently selected agent

        Returns:
            FormattedText with styled lines
        """
        prompt_symbol = settings.cli.prompt_style.strip()
        lines = []
        for i, agent in enumerate(agents):
            agent_name = agent.name
            alias = agent.llm.alias

            display_text = f"{agent_name} ({alias})"

            if i == selected_index:
                # Use direct color code for selected line
                lines.append(
                    (f"{theme.selection_color}", f"{prompt_symbol} {display_text}")
                )
            else:
                lines.append(("", f"  {display_text}"))

            if i < len(agents) - 1:
                lines.append(("", "\n"))

        return FormattedText(lines)
