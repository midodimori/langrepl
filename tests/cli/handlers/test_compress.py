"""Tests for compression handler."""

from unittest.mock import MagicMock, patch

import pytest
from langgraph.checkpoint.base import CheckpointTuple

from src.cli.handlers.compress import CompressionHandler
from src.core.config import CompressionConfig


class TestCompressionHandler:
    """Tests for CompressionHandler class."""

    @pytest.mark.asyncio
    @patch("src.cli.handlers.compress.initializer.load_agents_config")
    async def test_handle_with_agent_not_found(self, mock_load_agents, mock_session):
        """Test that handle shows error when agent not found."""
        handler = CompressionHandler(mock_session)

        mock_config_data = MagicMock()
        mock_config_data.get_agent_config.return_value = None
        mock_load_agents.return_value = mock_config_data

        await handler.handle()

        mock_load_agents.assert_called_once_with(mock_session.context.working_dir)

    @pytest.mark.asyncio
    @patch("src.cli.handlers.compress.initializer.load_agents_config")
    @patch("src.cli.handlers.compress.initializer.get_checkpointer")
    async def test_handle_with_no_checkpoint(
        self,
        mock_get_checkpointer,
        mock_load_agents,
        mock_session,
        mock_agent_config,
        mock_checkpointer,
    ):
        """Test that handle shows error when no checkpoint found."""
        handler = CompressionHandler(mock_session)

        mock_config_data = MagicMock()
        mock_config_data.get_agent_config.return_value = mock_agent_config
        mock_load_agents.return_value = mock_config_data

        mock_checkpointer.aget_tuple.return_value = None
        mock_get_checkpointer.return_value.__aenter__.return_value = mock_checkpointer

        await handler.handle()

        mock_checkpointer.aget_tuple.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.cli.handlers.compress.initializer.load_agents_config")
    @patch("src.cli.handlers.compress.initializer.get_checkpointer")
    async def test_handle_with_no_messages(
        self,
        mock_get_checkpointer,
        mock_load_agents,
        mock_session,
        mock_agent_config,
        mock_checkpointer,
        mock_checkpointer_tuple,
    ):
        """Test that handle shows error when no messages found."""
        handler = CompressionHandler(mock_session)

        mock_config_data = MagicMock()
        mock_config_data.get_agent_config.return_value = mock_agent_config
        mock_load_agents.return_value = mock_config_data

        checkpoint = mock_checkpointer_tuple.checkpoint.copy()
        checkpoint["channel_values"] = {"messages": []}
        empty_checkpoint = CheckpointTuple(
            config=mock_checkpointer_tuple.config,
            checkpoint=checkpoint,
            metadata=mock_checkpointer_tuple.metadata,
            parent_config=mock_checkpointer_tuple.parent_config,
            pending_writes=mock_checkpointer_tuple.pending_writes,
        )
        mock_checkpointer.aget_tuple.return_value = empty_checkpoint
        mock_get_checkpointer.return_value.__aenter__.return_value = mock_checkpointer

        await handler.handle()

    @pytest.mark.asyncio
    @patch("src.cli.handlers.compress.compress_messages")
    @patch("src.cli.handlers.compress.calculate_message_tokens")
    @patch("src.cli.handlers.compress.initializer.llm_factory")
    @patch("src.cli.handlers.compress.initializer.load_agents_config")
    @patch("src.cli.handlers.compress.initializer.get_checkpointer")
    async def test_handle_compresses_successfully(
        self,
        mock_get_checkpointer,
        mock_load_agents,
        mock_llm_factory,
        mock_calc_tokens,
        mock_compress,
        mock_session,
        mock_agent_config,
        mock_checkpointer,
        sample_messages,
        mock_checkpointer_tuple,
    ):
        """Test that handle compresses messages successfully."""
        handler = CompressionHandler(mock_session)

        mock_config_data = MagicMock()
        mock_config_data.get_agent_config.return_value = mock_agent_config
        mock_load_agents.return_value = mock_config_data

        checkpoint = mock_checkpointer_tuple.checkpoint.copy()
        checkpoint["channel_values"] = {"messages": sample_messages}
        checkpoint_with_messages = CheckpointTuple(
            config=mock_checkpointer_tuple.config,
            checkpoint=checkpoint,
            metadata=mock_checkpointer_tuple.metadata,
            parent_config=mock_checkpointer_tuple.parent_config,
            pending_writes=mock_checkpointer_tuple.pending_writes,
        )
        mock_checkpointer.aget_tuple.return_value = checkpoint_with_messages
        mock_get_checkpointer.return_value.__aenter__.return_value = mock_checkpointer

        mock_llm = MagicMock()
        mock_llm_factory.create.return_value = mock_llm

        mock_calc_tokens.side_effect = [1000, 500]
        mock_compress.return_value = [sample_messages[0]]

        with patch("src.cli.handlers.compress.console.console.status"):
            await handler.handle()

            mock_compress.assert_called_once()
            mock_session.graph.aupdate_state.assert_called_once()
            mock_session.update_context.assert_called_once()
            mock_session.renderer.render_message.assert_called()

    @pytest.mark.asyncio
    @patch("src.cli.handlers.compress.console.console.status")
    @patch("src.cli.handlers.compress.compress_messages")
    @patch("src.cli.handlers.compress.calculate_message_tokens")
    @patch("src.cli.handlers.compress.initializer.llm_factory")
    @patch("src.cli.handlers.compress.initializer.load_agents_config")
    @patch("src.cli.handlers.compress.initializer.get_checkpointer")
    async def test_handle_uses_custom_compression_config(
        self,
        mock_get_checkpointer,
        mock_load_agents,
        mock_llm_factory,
        mock_calc_tokens,
        mock_compress,
        mock_status,
        mock_session,
        mock_agent_config,
        mock_llm_config,
        mock_checkpointer,
        mock_checkpointer_tuple,
        sample_messages,
    ):
        """Test that handle uses custom compression config when available."""
        handler = CompressionHandler(mock_session)

        compression_llm = mock_llm_config.model_copy(
            update={"alias": "compression-model", "model": "claude-3-haiku-20240307"}
        )
        compression_config = CompressionConfig(compression_llm=compression_llm)
        mock_agent_config.compression = compression_config

        mock_config_data = MagicMock()
        mock_config_data.get_agent_config.return_value = mock_agent_config
        mock_load_agents.return_value = mock_config_data

        checkpoint = mock_checkpointer_tuple.checkpoint.copy()
        checkpoint["channel_values"] = {"messages": sample_messages}
        checkpoint_with_messages = CheckpointTuple(
            config=mock_checkpointer_tuple.config,
            checkpoint=checkpoint,
            metadata=mock_checkpointer_tuple.metadata,
            parent_config=mock_checkpointer_tuple.parent_config,
            pending_writes=mock_checkpointer_tuple.pending_writes,
        )
        mock_checkpointer.aget_tuple.return_value = checkpoint_with_messages
        mock_get_checkpointer.return_value.__aenter__.return_value = mock_checkpointer

        mock_llm_factory.create.return_value = MagicMock()
        mock_calc_tokens.return_value = 1000
        mock_compress.return_value = [sample_messages[0]]

        await handler.handle()

        mock_llm_factory.create.assert_called_once_with(compression_llm)

    @pytest.mark.asyncio
    @patch("src.cli.handlers.compress.initializer.load_agents_config")
    async def test_handle_with_exception(self, mock_load_agents, mock_session):
        """Test that handle handles exceptions gracefully."""
        handler = CompressionHandler(mock_session)
        mock_load_agents.side_effect = Exception("Test error")

        await handler.handle()

        mock_load_agents.assert_called_once()
