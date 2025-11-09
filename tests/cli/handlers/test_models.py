"""Tests for model handler."""

from unittest.mock import AsyncMock, patch

import pytest

from src.cli.handlers.models import ModelHandler
from src.core.config import AgentConfig


class TestModelHandler:
    """Tests for ModelHandler class."""

    @pytest.mark.asyncio
    @patch("src.cli.handlers.models.initializer.load_llms_config")
    @patch("src.cli.handlers.models.initializer.load_agent_config")
    async def test_handle_with_no_other_models(
        self,
        mock_load_agent,
        mock_load_llms,
        mock_session,
        mock_agent_config,
        mock_llms_config,
    ):
        """Test that handle shows error when no other models available."""
        handler = ModelHandler(mock_session)
        mock_load_agent.return_value = mock_agent_config

        mock_llms_config.llms = [mock_agent_config.llm]
        mock_load_llms.return_value = mock_llms_config

        with (
            patch.object(
                handler,
                "_get_agent_selection",
                return_value=("agent", "test-agent", mock_agent_config),
            ),
            patch("src.cli.handlers.models.console") as mock_console,
        ):
            await handler.handle()

            mock_load_agent.assert_called_once()
            mock_console.print_error.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.cli.handlers.models.initializer.update_agent_llm")
    @patch("src.cli.handlers.models.initializer.load_llms_config")
    @patch("src.cli.handlers.models.initializer.load_agent_config")
    async def test_handle_updates_agent_model(
        self,
        mock_load_agent,
        mock_load_llms,
        mock_update_llm,
        mock_session,
        mock_agent_config,
        mock_llm_config,
        mock_llms_config,
    ):
        """Test that handle updates agent model successfully."""
        handler = ModelHandler(mock_session)
        mock_load_agent.return_value = mock_agent_config

        alt_llm_config = mock_llm_config.model_copy(
            update={"alias": "alt-model", "model": "claude-3-opus-20240229"}
        )

        mock_llms_config.llms = [mock_agent_config.llm, alt_llm_config]
        mock_load_llms.return_value = mock_llms_config

        with (
            patch.object(
                handler,
                "_get_agent_selection",
                return_value=("agent", "test-agent", mock_agent_config),
            ),
            patch.object(handler, "_get_model_selection", return_value="alt-model"),
        ):
            await handler.handle()

            mock_update_llm.assert_called_once_with(
                "test-agent", "alt-model", mock_session.context.working_dir
            )
            mock_session.update_context.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.cli.handlers.models.initializer.update_subagent_llm")
    @patch("src.cli.handlers.models.initializer.load_llms_config")
    @patch("src.cli.handlers.models.initializer.load_agent_config")
    async def test_handle_updates_subagent_model(
        self,
        mock_load_agent,
        mock_load_llms,
        mock_update_subagent_llm,
        mock_session,
        mock_agent_config,
        mock_llm_config,
        mock_llms_config,
    ):
        """Test that handle updates subagent model successfully."""
        handler = ModelHandler(mock_session)

        subagent_llm = mock_llm_config.model_copy(
            update={"alias": "subagent-model", "model": "claude-3-haiku-20240307"}
        )
        subagent = AgentConfig(name="subagent-1", llm=subagent_llm, prompt="")
        mock_agent_config.subagents = [subagent]
        mock_load_agent.return_value = mock_agent_config

        alt_llm_config = mock_llm_config.model_copy(
            update={"alias": "alt-model", "model": "claude-3-opus-20240229"}
        )

        mock_llms_config.llms = [subagent_llm, alt_llm_config]
        mock_load_llms.return_value = mock_llms_config

        with (
            patch.object(
                handler,
                "_get_agent_selection",
                return_value=("subagent", "subagent-1", subagent),
            ),
            patch.object(handler, "_get_model_selection", return_value="alt-model"),
        ):
            await handler.handle()

            mock_update_subagent_llm.assert_called_once_with(
                "subagent-1", "alt-model", mock_session.context.working_dir
            )

    @pytest.mark.asyncio
    @patch("src.cli.handlers.models.Application")
    async def test_get_agent_selection_with_no_agents(self, mock_app_cls, mock_session):
        """Test that _get_agent_selection returns None for empty list."""
        handler = ModelHandler(mock_session)

        result = await handler._get_agent_selection([])

        assert result is None
        mock_app_cls.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.cli.handlers.models.Application")
    async def test_get_agent_selection_with_selection(
        self, mock_app_cls, mock_session, mock_agent_config
    ):
        """Test that _get_agent_selection returns selected agent."""
        handler = ModelHandler(mock_session)

        agents = [("agent", "test-agent", mock_agent_config)]

        mock_app = AsyncMock()
        mock_app.run_async = AsyncMock()
        mock_app_cls.return_value = mock_app

        with patch("src.cli.handlers.models.sys.stdout"):
            await handler._get_agent_selection(agents)
            mock_app.run_async.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.cli.handlers.models.Application")
    async def test_get_agent_selection_keyboard_interrupt(
        self, mock_app_cls, mock_session, mock_agent_config
    ):
        """Test that _get_agent_selection handles KeyboardInterrupt."""
        handler = ModelHandler(mock_session)

        agents = [("agent", "test-agent", mock_agent_config)]

        mock_app = AsyncMock()
        mock_app.run_async = AsyncMock(side_effect=KeyboardInterrupt())
        mock_app_cls.return_value = mock_app

        result = await handler._get_agent_selection(agents)

        assert result is None

    @pytest.mark.asyncio
    @patch("src.cli.handlers.models.Application")
    async def test_get_model_selection_with_no_models(self, mock_app_cls, mock_session):
        """Test that _get_model_selection returns empty string for no models."""
        handler = ModelHandler(mock_session)

        result = await handler._get_model_selection([], "test-model", "test-model")

        assert result == ""
        mock_app_cls.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.cli.handlers.models.Application")
    async def test_get_model_selection_with_selection(
        self, mock_app_cls, mock_session, mock_llm_config
    ):
        """Test that _get_model_selection returns selected model."""
        handler = ModelHandler(mock_session)

        mock_app = AsyncMock()
        mock_app.run_async = AsyncMock()
        mock_app_cls.return_value = mock_app

        with patch("src.cli.handlers.models.sys.stdout"):
            await handler._get_model_selection(
                [mock_llm_config], "test-model", "test-model"
            )
            mock_app.run_async.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.cli.handlers.models.Application")
    async def test_get_model_selection_keyboard_interrupt(
        self, mock_app_cls, mock_session, mock_llm_config
    ):
        """Test that _get_model_selection handles KeyboardInterrupt."""
        handler = ModelHandler(mock_session)

        mock_app = AsyncMock()
        mock_app.run_async = AsyncMock(side_effect=KeyboardInterrupt())
        mock_app_cls.return_value = mock_app

        result = await handler._get_model_selection(
            [mock_llm_config], "test-model", "test-model"
        )

        assert result == ""

    def test_format_agent_list_formats_correctly(self, mock_session, mock_agent_config):
        """Test that _format_agent_list formats agents correctly."""
        handler = ModelHandler(mock_session)
        agents = [("agent", "test-agent", mock_agent_config)]

        formatted = handler._format_agent_list(agents, 0)

        assert formatted is not None
        # Verify the formatted text contains the agent name and model
        formatted_str = "".join(str(item[1]) for item in formatted)
        assert "test-agent" in formatted_str
        # Should show context model for main agent
        assert mock_session.context.model in formatted_str

    def test_format_model_list_formats_correctly(self, mock_llm_config):
        """Test that _format_model_list formats models correctly."""
        formatted = ModelHandler._format_model_list(
            [mock_llm_config], 0, "test-model", "test-model"
        )

        assert formatted is not None
        # Verify the formatted text contains the model name and indicators
        formatted_str = "".join(str(item[1]) for item in formatted)
        assert mock_llm_config.alias in formatted_str

    @pytest.mark.asyncio
    @patch("src.cli.handlers.models.initializer.load_agent_config")
    async def test_handle_with_exception(self, mock_load_agent, mock_session):
        """Test that handle handles exceptions gracefully."""
        handler = ModelHandler(mock_session)
        mock_load_agent.side_effect = Exception("Test error")

        await handler.handle()

        mock_load_agent.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.cli.handlers.models.initializer.load_llms_config")
    @patch("src.cli.handlers.models.initializer.load_agent_config")
    async def test_handle_cancelled_agent_selection(
        self, mock_load_agent, mock_load_llms, mock_session, mock_agent_config
    ):
        """Test that handle returns when agent selection is cancelled."""
        handler = ModelHandler(mock_session)
        mock_load_agent.return_value = mock_agent_config

        with patch.object(handler, "_get_agent_selection", return_value=None):
            await handler.handle()

            mock_load_llms.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.cli.handlers.models.initializer.load_llms_config")
    @patch("src.cli.handlers.models.initializer.load_agent_config")
    async def test_handle_cancelled_model_selection(
        self,
        mock_load_agent,
        mock_load_llms,
        mock_session,
        mock_agent_config,
        mock_llm_config,
        mock_llms_config,
    ):
        """Test that handle returns when model selection is cancelled."""
        handler = ModelHandler(mock_session)
        mock_load_agent.return_value = mock_agent_config

        alt_llm_config = mock_llm_config.model_copy(
            update={"alias": "alt-model", "model": "claude-3-opus-20240229"}
        )

        mock_llms_config.llms = [mock_agent_config.llm, alt_llm_config]
        mock_load_llms.return_value = mock_llms_config

        with (
            patch.object(
                handler,
                "_get_agent_selection",
                return_value=("agent", "test-agent", mock_agent_config),
            ),
            patch.object(handler, "_get_model_selection", return_value=""),
        ):
            await handler.handle()

            mock_session.update_context.assert_not_called()
