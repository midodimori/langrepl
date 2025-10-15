from unittest.mock import AsyncMock, Mock

import pytest

from src.checkpointer.utils import get_checkpoint_history


class TestGetCheckpointHistory:
    @pytest.mark.asyncio
    async def test_single_checkpoint_no_parent(self):
        mock_checkpointer = Mock()
        mock_checkpoint = Mock()
        mock_checkpoint.parent_config = None

        result = await get_checkpoint_history(mock_checkpointer, mock_checkpoint)

        assert len(result) == 1
        assert result[0] == mock_checkpoint

    @pytest.mark.asyncio
    async def test_multiple_checkpoints_linear_history(self):
        mock_checkpointer = Mock()

        checkpoint3 = Mock()
        checkpoint3.parent_config = Mock()

        checkpoint2 = Mock()
        checkpoint2.parent_config = Mock()

        checkpoint1 = Mock()
        checkpoint1.parent_config = None

        mock_checkpointer.aget_tuple = AsyncMock(side_effect=[checkpoint2, checkpoint1])

        result = await get_checkpoint_history(mock_checkpointer, checkpoint3)

        assert len(result) == 3
        assert result[0] == checkpoint1
        assert result[1] == checkpoint2
        assert result[2] == checkpoint3

    @pytest.mark.asyncio
    async def test_returns_chronological_order(self):
        mock_checkpointer = Mock()

        latest = Mock()
        latest.parent_config = Mock()
        latest.checkpoint = {"id": "3"}

        middle = Mock()
        middle.parent_config = Mock()
        middle.checkpoint = {"id": "2"}

        oldest = Mock()
        oldest.parent_config = None
        oldest.checkpoint = {"id": "1"}

        mock_checkpointer.aget_tuple = AsyncMock(side_effect=[middle, oldest])

        result = await get_checkpoint_history(mock_checkpointer, latest)

        assert result[0] == oldest
        assert result[1] == middle
        assert result[2] == latest

    @pytest.mark.asyncio
    async def test_stops_at_none_parent(self):
        mock_checkpointer = Mock()

        checkpoint2 = Mock()
        checkpoint2.parent_config = Mock()

        checkpoint1 = Mock()
        checkpoint1.parent_config = None

        mock_checkpointer.aget_tuple = AsyncMock(return_value=checkpoint1)

        result = await get_checkpoint_history(mock_checkpointer, checkpoint2)

        assert len(result) == 2
        mock_checkpointer.aget_tuple.assert_called_once()
