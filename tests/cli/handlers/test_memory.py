"""Tests for memory handler."""

import subprocess
from unittest.mock import patch

import pytest

from src.cli.handlers.memory import MemoryHandler
from src.core.constants import CONFIG_MEMORY_FILE_NAME


class TestMemoryHandler:
    """Tests for MemoryHandler class."""

    @pytest.mark.asyncio
    @patch("subprocess.run")
    async def test_handle_opens_editor_successfully(self, mock_run, mock_session):
        """Test that handle opens the editor successfully."""
        handler = MemoryHandler(mock_session)
        memory_path = mock_session.context.working_dir / CONFIG_MEMORY_FILE_NAME

        await handler.handle()

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert str(memory_path) in args
        assert mock_session.needs_reload is True
        assert mock_session.running is False

    @pytest.mark.asyncio
    @patch("subprocess.run")
    async def test_handle_creates_directory_if_missing(self, mock_run, mock_session):
        """Test that handle creates .langrepl directory if it doesn't exist."""
        handler = MemoryHandler(mock_session)
        memory_path = mock_session.context.working_dir / CONFIG_MEMORY_FILE_NAME

        if memory_path.parent.exists():
            memory_path.parent.rmdir()

        await handler.handle()

        assert memory_path.parent.exists()

    @pytest.mark.asyncio
    @patch("subprocess.run")
    async def test_handle_with_editor_error(self, mock_run, mock_session):
        """Test that handle handles editor errors gracefully."""
        handler = MemoryHandler(mock_session)
        mock_run.side_effect = subprocess.CalledProcessError(1, "vim")

        await handler.handle()

        assert mock_session.needs_reload is False
        assert mock_session.running is True

    @pytest.mark.asyncio
    @patch("subprocess.run")
    async def test_handle_with_editor_not_found(self, mock_run, mock_session):
        """Test that handle handles missing editor gracefully."""
        handler = MemoryHandler(mock_session)
        mock_run.side_effect = FileNotFoundError("nonexistent_editor not found")

        await handler.handle()

        assert mock_session.needs_reload is False
        assert mock_session.running is True

    @pytest.mark.asyncio
    @patch("src.cli.handlers.memory.settings")
    @patch("subprocess.run")
    async def test_handle_uses_editor_from_settings(
        self, mock_run, mock_settings, mock_session
    ):
        """Test that handle uses the editor from settings."""
        handler = MemoryHandler(mock_session)
        mock_settings.cli.editor = "nano"

        await handler.handle()

        args = mock_run.call_args[0][0]
        assert args[0] == "nano"
