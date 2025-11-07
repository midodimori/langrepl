"""Tests for CLI session module."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.cli.core.session import Session


class TestSessionInit:
    """Tests for Session initialization."""

    def test_init_creates_all_components(self, mock_context):
        """Test that __init__ creates all required components."""
        session = Session(mock_context)

        assert session.context == mock_context
        assert session.renderer is not None
        assert session.command_dispatcher is not None
        assert session.message_dispatcher is not None
        assert session.prompt is not None

    def test_init_sets_default_state(self, mock_context):
        """Test that __init__ sets default session state."""
        session = Session(mock_context)

        assert session.graph is None
        assert session.graph_context is None
        assert session.running is False
        assert session.needs_reload is False
        assert session.prefilled_text is None
        assert session.prefilled_reference_mapping == {}

    @patch("src.cli.core.session.InteractivePrompt")
    def test_init_registers_mode_change_callback(
        self,
        mock_prompt_cls,
        mock_context,
    ):
        """Test that __init__ registers approval mode change callback."""
        mock_prompt = MagicMock()
        mock_prompt_cls.return_value = mock_prompt

        Session(mock_context)

        mock_prompt.set_mode_change_callback.assert_called_once()
        callback = mock_prompt.set_mode_change_callback.call_args[0][0]
        assert callable(callback)


class TestSessionStart:
    """Tests for Session.start() method."""

    @pytest.mark.asyncio
    @patch.object(Session, "_main_loop", new_callable=AsyncMock)
    @patch("src.cli.core.session.initializer.get_graph")
    async def test_start_loads_graph(
        self,
        mock_get_graph,
        _mock_main_loop,
        mock_context,
    ):
        """Test that start() loads the graph."""
        graph_instance = MagicMock()

        @asynccontextmanager
        async def graph_context(*args, **kwargs):
            yield graph_instance

        mock_get_graph.side_effect = graph_context
        session = Session(mock_context)

        await session.start()

        assert session.graph is graph_instance

    @pytest.mark.asyncio
    @patch.object(Session, "_main_loop", new_callable=AsyncMock)
    @patch("src.cli.core.session.initializer.get_graph")
    async def test_start_shows_welcome_by_default(
        self,
        mock_get_graph,
        _mock_main_loop,
        mock_context,
    ):
        """Test that start() shows welcome message by default."""
        graph_instance = MagicMock()

        @asynccontextmanager
        async def graph_context(*args, **kwargs):
            yield graph_instance

        mock_get_graph.side_effect = graph_context
        session = Session(mock_context)
        session.renderer = MagicMock()

        await session.start()

        session.renderer.show_welcome.assert_called_once_with(mock_context)

    @pytest.mark.asyncio
    @patch.object(Session, "_main_loop", new_callable=AsyncMock)
    @patch("src.cli.core.session.initializer.get_graph")
    async def test_start_hides_welcome_when_requested(
        self,
        mock_get_graph,
        _mock_main_loop,
        mock_context,
    ):
        """Test that start() hides welcome message when show_welcome=False."""
        graph_instance = MagicMock()

        @asynccontextmanager
        async def graph_context(*args, **kwargs):
            yield graph_instance

        mock_get_graph.side_effect = graph_context
        session = Session(mock_context)
        session.renderer = MagicMock()

        await session.start(show_welcome=False)

        session.renderer.show_welcome.assert_not_called()

    @pytest.mark.asyncio
    @patch.object(Session, "_main_loop", new_callable=AsyncMock)
    @patch("src.cli.core.session.initializer.get_graph")
    async def test_start_calls_main_loop(
        self,
        mock_get_graph,
        mock_main_loop,
        mock_context,
    ):
        """Test that start() calls main loop."""
        graph_instance = MagicMock()

        @asynccontextmanager
        async def graph_context(*args, **kwargs):
            yield graph_instance

        mock_get_graph.side_effect = graph_context
        session = Session(mock_context)

        await session.start()

        mock_main_loop.assert_called_once()


class TestSessionUpdateContext:
    """Tests for Session.update_context() method."""

    def test_update_context_updates_single_field(self, mock_context):
        """Test that update_context() updates a single field."""
        session = Session(mock_context)
        original_value = mock_context.current_input_tokens

        session.update_context(current_input_tokens=1000)

        assert mock_context.current_input_tokens == 1000
        assert mock_context.current_input_tokens != original_value

    def test_update_context_updates_multiple_fields(self, mock_context):
        """Test that update_context() updates multiple fields at once."""
        session = Session(mock_context)

        session.update_context(
            current_input_tokens=1000, current_output_tokens=2000, total_cost=3.5
        )

        assert mock_context.current_input_tokens == 1000
        assert mock_context.current_output_tokens == 2000
        assert mock_context.total_cost == 3.5

    def test_update_context_with_agent_triggers_reload(self, mock_context):
        """Test that updating agent triggers reload."""
        session = Session(mock_context)
        session.running = True
        session.needs_reload = False

        session.update_context(agent="new-agent")

        assert session.needs_reload is True
        assert session.running is False

    def test_update_context_with_model_triggers_reload(self, mock_context):
        """Test that updating model triggers reload."""
        session = Session(mock_context)
        session.running = True
        session.needs_reload = False

        session.update_context(model="new-model")

        assert session.needs_reload is True
        assert session.running is False

    def test_update_context_with_both_agent_and_model_triggers_reload(
        self, mock_context
    ):
        """Test that updating both agent and model triggers reload."""
        session = Session(mock_context)
        session.running = True
        session.needs_reload = False

        session.update_context(agent="new-agent", model="new-model")

        assert session.needs_reload is True
        assert session.running is False

    def test_update_context_with_tokens_does_not_trigger_reload(self, mock_context):
        """Test that updating tokens doesn't trigger reload."""
        session = Session(mock_context)
        session.running = True
        session.needs_reload = False

        session.update_context(current_input_tokens=1000)

        assert session.needs_reload is False
        assert session.running is True

    def test_update_context_ignores_invalid_fields(self, mock_context):
        """Test that update_context() ignores fields not in context."""
        session = Session(mock_context)

        session.update_context(invalid_field="value")

        assert not hasattr(mock_context, "invalid_field")

    def test_update_context_with_thread_id(self, mock_context):
        """Test that update_context() can update thread_id."""
        session = Session(mock_context)
        new_thread_id = "new-thread-123"

        session.update_context(thread_id=new_thread_id)

        assert mock_context.thread_id == new_thread_id


class TestSessionHandleApprovalModeChange:
    """Tests for Session._handle_approval_mode_change() method."""

    def test_handle_approval_mode_change_cycles_mode(self, mock_context):
        """Test that _handle_approval_mode_change cycles approval mode."""
        session = Session(mock_context)
        original_mode = mock_context.approval_mode

        session._handle_approval_mode_change()

        assert mock_context.approval_mode != original_mode

    def test_handle_approval_mode_change_refreshes_prompt_style(self, mock_context):
        """Test that _handle_approval_mode_change refreshes prompt style."""
        session = Session(mock_context)
        session.prompt = MagicMock()

        session._handle_approval_mode_change()

        session.prompt.refresh_style.assert_called_once()
