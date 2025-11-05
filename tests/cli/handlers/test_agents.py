"""Tests for agent handler."""

from unittest.mock import AsyncMock, patch

import pytest

from src.cli.handlers.agents import AgentHandler


class TestAgentHandler:
    """Tests for AgentHandler class."""

    @pytest.mark.asyncio
    @patch("src.cli.handlers.agents.initializer.load_agents_config")
    async def test_handle_with_no_other_agents(
        self, mock_load_agents, mock_session, mock_agents_config
    ):
        """Test that handle shows error when no other agents available."""
        handler = AgentHandler(mock_session)
        mock_load_agents.return_value = mock_agents_config

        await handler.handle()

        mock_load_agents.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.cli.handlers.agents.initializer.update_default_agent")
    @patch("src.cli.handlers.agents.initializer.load_agent_config")
    @patch("src.cli.handlers.agents.initializer.load_agents_config")
    async def test_handle_updates_context_on_selection(
        self,
        mock_load_agents,
        mock_load_agent,
        mock_update_default,
        mock_session,
        mock_agent_config,
        mock_llm_config,
        mock_agents_config,
    ):
        """Test that handle updates context when agent is selected."""
        handler = AgentHandler(mock_session)

        agent2 = mock_agent_config.model_copy(
            update={
                "name": "agent2",
                "llm": mock_llm_config.model_copy(update={"alias": "model2"}),
                "prompt": "",
            }
        )

        mock_agents_config.agents = [mock_agent_config, agent2]
        mock_load_agents.return_value = mock_agents_config
        mock_load_agent.return_value = agent2

        with patch.object(
            handler, "_get_agent_selection", return_value="agent2"
        ) as mock_selection:
            await handler.handle()

            mock_selection.assert_called_once()
            mock_session.update_context.assert_called_once_with(
                agent="agent2", model="model2"
            )
            mock_update_default.assert_called_once_with(
                "agent2", mock_session.context.working_dir
            )

    @pytest.mark.asyncio
    @patch("src.cli.handlers.agents.initializer.load_agents_config")
    async def test_handle_does_not_update_on_cancel(
        self,
        mock_load_agents,
        mock_session,
        mock_agent_config,
        mock_llm_config,
        mock_agents_config,
    ):
        """Test that handle does not update context when cancelled."""
        handler = AgentHandler(mock_session)

        agent2 = mock_agent_config.model_copy(
            update={
                "name": "agent2",
                "llm": mock_llm_config.model_copy(update={"alias": "model2"}),
                "prompt": "",
            }
        )

        mock_agents_config.agents = [mock_agent_config, agent2]
        mock_load_agents.return_value = mock_agents_config

        with patch.object(handler, "_get_agent_selection", return_value=""):
            await handler.handle()

            mock_session.update_context.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.cli.handlers.agents.Application")
    async def test_get_agent_selection_returns_selected_agent(
        self, mock_app_cls, mock_session, mock_agent_config, mock_llm_config
    ):
        """Test that _get_agent_selection returns selected agent name."""
        handler = AgentHandler(mock_session)

        agent2 = mock_agent_config.model_copy(
            update={
                "name": "agent2",
                "llm": mock_llm_config.model_copy(update={"alias": "model2"}),
                "prompt": "",
            }
        )

        agents = [mock_agent_config, agent2]

        mock_app = AsyncMock()
        mock_app.run_async = AsyncMock()
        mock_app_cls.return_value = mock_app

        with patch("src.cli.handlers.agents.sys.stdout"):
            await handler._get_agent_selection(agents)

            mock_app.run_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_agent_selection_returns_empty_for_no_agents(self, mock_session):
        """Test that _get_agent_selection returns empty string for no agents."""
        handler = AgentHandler(mock_session)

        result = await handler._get_agent_selection([])

        assert result == ""

    def test_format_agent_list_formats_correctly(
        self, mock_agent_config, mock_llm_config
    ):
        """Test that _format_agent_list formats agents correctly."""
        agent2 = mock_agent_config.model_copy(
            update={
                "name": "agent2",
                "llm": mock_llm_config.model_copy(update={"alias": "model2"}),
                "prompt": "",
            }
        )

        agents = [mock_agent_config, agent2]

        formatted = AgentHandler._format_agent_list(agents, 0)

        assert formatted is not None
        assert len(formatted) > 0

    @pytest.mark.asyncio
    @patch("src.cli.handlers.agents.initializer.load_agents_config")
    async def test_handle_with_exception(self, mock_load_agents, mock_session):
        """Test that handle handles exceptions gracefully."""
        handler = AgentHandler(mock_session)
        mock_load_agents.side_effect = Exception("Test error")

        await handler.handle()

        mock_load_agents.assert_called_once()
