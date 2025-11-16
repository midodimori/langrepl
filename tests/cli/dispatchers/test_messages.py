"""Tests for message dispatcher."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Interrupt

from src.cli.dispatchers.messages import MessageDispatcher


class TestMessageDispatcher:
    """Tests for MessageDispatcher class."""

    def test_init_creates_dispatcher(self, mock_session):
        """Test that __init__ creates dispatcher with handlers."""
        dispatcher = MessageDispatcher(mock_session)

        assert dispatcher.session == mock_session
        assert dispatcher.interrupt_handler is not None

    @pytest.mark.asyncio
    @patch.object(MessageDispatcher, "_stream_response", new_callable=AsyncMock)
    async def test_dispatch_creates_human_message(
        self,
        mock_stream_response,
        mock_session,
    ):
        """Test dispatch creates HumanMessage."""
        dispatcher = MessageDispatcher(mock_session)

        await dispatcher.dispatch("test message")

        mock_stream_response.assert_called_once()
        call_args = mock_stream_response.call_args[0]
        input_data = call_args[0]
        assert "messages" in input_data
        assert isinstance(input_data["messages"][0], HumanMessage)
        assert input_data["messages"][0].content == "test message"

    @pytest.mark.asyncio
    @patch.object(MessageDispatcher, "_stream_response", new_callable=AsyncMock)
    async def test_dispatch_stores_short_content(
        self,
        mock_stream_response,
        mock_session,
    ):
        """Test dispatch stores original content as short_content."""
        dispatcher = MessageDispatcher(mock_session)

        await dispatcher.dispatch("original")

        call_args = mock_stream_response.call_args[0]
        input_data = call_args[0]
        assert input_data["messages"][0].short_content == "original"

    @pytest.mark.asyncio
    @patch.object(MessageDispatcher, "_stream_response", new_callable=AsyncMock)
    async def test_dispatch_includes_reference_mapping(
        self,
        mock_stream_response,
        mock_session,
    ):
        """Test dispatch includes reference mapping in additional_kwargs."""
        dispatcher = MessageDispatcher(mock_session)
        mock_session.prefilled_reference_mapping = {"ref1": "path1"}

        await dispatcher.dispatch("test")

        call_args = mock_stream_response.call_args[0]
        input_data = call_args[0]
        assert "reference_mapping" in input_data["messages"][0].additional_kwargs
        assert input_data["messages"][0].additional_kwargs["reference_mapping"] == {
            "ref1": "path1"
        }

    @pytest.mark.asyncio
    @patch.object(MessageDispatcher, "_stream_response", new_callable=AsyncMock)
    async def test_dispatch_clears_prefilled_mapping(
        self,
        mock_stream_response,
        mock_session,
    ):
        """Test dispatch clears prefilled reference mapping."""
        dispatcher = MessageDispatcher(mock_session)
        mock_session.prefilled_reference_mapping = {"ref1": "path1"}

        await dispatcher.dispatch("test")

        mock_stream_response.assert_called_once()
        assert mock_session.prefilled_reference_mapping == {}

    @pytest.mark.asyncio
    @patch.object(MessageDispatcher, "_stream_response", new_callable=AsyncMock)
    async def test_dispatch_creates_graph_config(
        self,
        mock_stream_response,
        mock_session,
        mock_context,
    ):
        """Test dispatch creates proper graph config and context."""
        mock_session.context = mock_context
        dispatcher = MessageDispatcher(mock_session)

        await dispatcher.dispatch("test")

        call_args = mock_stream_response.call_args[0]
        config = call_args[1]
        agent_context = call_args[2]

        # Check config structure
        assert "configurable" in config
        assert config["configurable"]["thread_id"] == mock_context.thread_id
        assert config["recursion_limit"] == mock_context.recursion_limit

        # Check agent context (approval_mode moved here in v1)
        assert agent_context.approval_mode == mock_context.approval_mode
        assert agent_context.working_dir == mock_context.working_dir

    @pytest.mark.asyncio
    @patch.object(
        MessageDispatcher,
        "_stream_response",
        new_callable=AsyncMock,
        side_effect=Exception("Test error"),
    )
    async def test_dispatch_handles_exceptions(
        self,
        mock_stream_response,
        mock_session,
    ):
        """Test dispatch handles exceptions gracefully."""
        dispatcher = MessageDispatcher(mock_session)

        # Should not raise, just log error
        await dispatcher.dispatch("test")

    def test_extract_interrupts_from_tuple(self):
        """Test _extract_interrupts with tuple format."""
        interrupt = Interrupt(value="test")
        chunk = ((), "updates", {"__interrupt__": [interrupt]})

        result = MessageDispatcher._extract_interrupts(chunk)

        assert result == [interrupt]

    def test_extract_interrupts_from_dict(self):
        """Test _extract_interrupts with dict format."""
        interrupt = Interrupt(value="test")
        chunk = {"__interrupt__": [interrupt]}

        result = MessageDispatcher._extract_interrupts(chunk)

        assert result == [interrupt]

    def test_extract_interrupts_no_interrupt(self):
        """Test _extract_interrupts with no interrupt."""
        chunk: tuple = ((), "updates", {"messages": []})

        result = MessageDispatcher._extract_interrupts(chunk)

        assert result is None

    def test_extract_interrupts_invalid_format(self):
        """Test _extract_interrupts with invalid format."""
        chunk: str = "invalid"

        result = MessageDispatcher._extract_interrupts(chunk)

        assert result is None

    @pytest.mark.asyncio
    async def test_process_update_chunk_renders_ai_message(self, mock_session):
        """Test _process_update_chunk renders AI messages."""
        dispatcher = MessageDispatcher(mock_session)
        mock_session.renderer.render_message = MagicMock()

        message = AIMessage(content="test", id="msg1")
        chunk = {"agent": {"messages": [message]}}
        rendered_messages: set[str] = set()

        await dispatcher._process_update_chunk(chunk, rendered_messages)

        mock_session.renderer.render_message.assert_called_once_with(message)
        assert "msg1_ai" in rendered_messages

    @pytest.mark.asyncio
    async def test_process_update_chunk_renders_tool_message(self, mock_session):
        """Test _process_update_chunk renders tool messages."""
        dispatcher = MessageDispatcher(mock_session)
        mock_session.renderer.render_message = MagicMock()

        message = ToolMessage(content="test", tool_call_id="tool1", id="msg1")
        chunk = {"agent": {"messages": [message]}}
        rendered_messages: set[str] = set()

        await dispatcher._process_update_chunk(chunk, rendered_messages)

        mock_session.renderer.render_message.assert_called_once_with(message)
        assert "msg1_tool" in rendered_messages

    @pytest.mark.asyncio
    async def test_process_update_chunk_skips_other_message_types(self, mock_session):
        """Test _process_update_chunk skips non-AI/Tool messages (e.g., HumanMessage)."""
        dispatcher = MessageDispatcher(mock_session)
        mock_session.renderer.render_message = MagicMock()

        message = HumanMessage(content="test", id="msg1")
        chunk = {"agent": {"messages": [message]}}
        rendered_messages: set[str] = set()

        await dispatcher._process_update_chunk(chunk, rendered_messages)

        mock_session.renderer.render_message.assert_not_called()
        assert "msg1_human" in rendered_messages

    @pytest.mark.asyncio
    @patch.object(MessageDispatcher, "_check_auto_compression", new_callable=AsyncMock)
    async def test_process_update_chunk_skips_rendered_messages(
        self,
        _mock_auto_compress,
        mock_session,
    ):
        """Test _process_update_chunk skips already rendered messages."""
        dispatcher = MessageDispatcher(mock_session)
        mock_session.renderer.render_message = MagicMock()

        message = AIMessage(content="test", id="msg1")
        chunk = {"agent": {"messages": [message]}}
        rendered_messages: set[str] = {"msg1_ai"}  # Already rendered

        await dispatcher._process_update_chunk(chunk, rendered_messages)

        mock_session.renderer.render_message.assert_not_called()

    @pytest.mark.asyncio
    @patch.object(MessageDispatcher, "_check_auto_compression", new_callable=AsyncMock)
    async def test_process_update_chunk_updates_context_for_ai_message(
        self,
        _mock_auto_compress,
        mock_session,
    ):
        """Test _process_update_chunk updates context for AI messages."""
        dispatcher = MessageDispatcher(mock_session)
        mock_session.renderer.render_message = MagicMock()
        mock_session.update_context = MagicMock()

        message = AIMessage(content="test", id="msg1")
        chunk = {
            "agent": {
                "messages": [message],
                "current_input_tokens": 100,
                "current_output_tokens": 50,
                "total_cost": 0.01,
            }
        }
        rendered_messages: set[str] = set()

        await dispatcher._process_update_chunk(chunk, rendered_messages)

        mock_session.update_context.assert_called_once_with(
            current_input_tokens=100, current_output_tokens=50, total_cost=0.01
        )

    @pytest.mark.asyncio
    @patch.object(MessageDispatcher, "_check_auto_compression", new_callable=AsyncMock)
    async def test_process_update_chunk_checks_auto_compression(
        self,
        mock_auto_compress,
        mock_session,
    ):
        """Test _process_update_chunk checks auto compression when token fields present."""
        dispatcher = MessageDispatcher(mock_session)
        mock_session.renderer.render_message = MagicMock()
        mock_session.update_context = MagicMock()

        message = AIMessage(content="test", id="msg1")
        # Include token fields to trigger auto-compression check
        chunk = {
            "agent": {
                "messages": [message],
                "current_input_tokens": 100,
            }
        }
        rendered_messages: set[str] = set()

        await dispatcher._process_update_chunk(chunk, rendered_messages)

        mock_auto_compress.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_update_chunk_no_messages(self, mock_session):
        """Test _process_update_chunk with no messages."""
        dispatcher = MessageDispatcher(mock_session)
        mock_session.renderer.render_message = MagicMock()

        chunk: dict = {"agent": {}}
        rendered_messages: set[str] = set()

        await dispatcher._process_update_chunk(chunk, rendered_messages)

        mock_session.renderer.render_message.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.cli.dispatchers.messages.initializer")
    async def test_check_auto_compression_disabled(
        self,
        mock_initializer,
        mock_session,
        mock_context,
    ):
        """Test _check_auto_compression when disabled."""
        dispatcher = MessageDispatcher(mock_session)
        mock_session.context = mock_context
        mock_agent_config = MagicMock()
        mock_agent_config.compression = None
        mock_initializer.load_agents_config = AsyncMock(
            return_value=MagicMock(
                get_agent_config=MagicMock(return_value=mock_agent_config)
            )
        )

        # Should return early without error
        await dispatcher._check_auto_compression()

    @pytest.mark.asyncio
    @patch("src.cli.dispatchers.messages.initializer")
    async def test_check_auto_compression_handles_exceptions(
        self,
        mock_initializer,
        mock_session,
    ):
        """Test _check_auto_compression handles exceptions gracefully."""
        dispatcher = MessageDispatcher(mock_session)
        mock_initializer.load_agents_config = AsyncMock(
            side_effect=Exception("Test error")
        )

        # Should not raise, just log
        await dispatcher._check_auto_compression()
