"""Tests for skills handler."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.cli.handlers.skills import SkillsHandler
from src.skills.factory import Skill


@pytest.fixture
def create_mock_skill():
    """Create a mock skill factory."""

    def _create(name: str, category: str = "test") -> Skill:
        skill = MagicMock(spec=Skill)
        skill.name = name
        skill.category = category
        skill.description = f"Description for {name}"
        skill.path = Path(f"/test/{category}/{name}/SKILL.md")
        skill.allowed_tools = None
        return skill

    return _create


class TestSkillsHandler:
    """Tests for SkillsHandler class."""

    @pytest.mark.asyncio
    async def test_handle_with_no_skills(self, mock_session):
        """Test that handle shows error when no skills available."""
        handler = SkillsHandler(mock_session)

        with patch("src.cli.handlers.skills.console") as mock_console:
            await handler.handle([])
            mock_console.print_error.assert_called_once_with("No skills available")

    @pytest.mark.asyncio
    async def test_handle_with_skills(self, mock_session, create_mock_skill):
        """Test that handle displays skills successfully."""
        handler = SkillsHandler(mock_session)
        skills = [create_mock_skill("skill1"), create_mock_skill("skill2")]

        with patch.object(
            handler, "_get_skill_selection", new_callable=AsyncMock
        ) as mock_selection:
            await handler.handle(skills)
            mock_selection.assert_called_once_with(skills)

    @pytest.mark.asyncio
    @patch("src.cli.handlers.skills.Application")
    async def test_get_skill_selection_displays_skills(
        self, mock_app_cls, mock_session, create_mock_skill
    ):
        """Test that _get_skill_selection displays skills."""
        handler = SkillsHandler(mock_session)
        skills = [create_mock_skill("skill1"), create_mock_skill("skill2")]

        mock_app = AsyncMock()
        mock_app.run_async = AsyncMock()
        mock_app_cls.return_value = mock_app

        await handler._get_skill_selection(skills)
        mock_app.run_async.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.cli.handlers.skills.Application")
    async def test_get_skill_selection_keyboard_interrupt(
        self, mock_app_cls, mock_session, create_mock_skill
    ):
        """Test that _get_skill_selection handles KeyboardInterrupt."""
        handler = SkillsHandler(mock_session)
        skills = [create_mock_skill("skill1")]

        mock_app = AsyncMock()
        mock_app.run_async = AsyncMock(side_effect=KeyboardInterrupt())
        mock_app_cls.return_value = mock_app

        await handler._get_skill_selection(skills)

    @pytest.mark.asyncio
    @patch("src.cli.handlers.skills.Application")
    async def test_get_skill_selection_eof_error(
        self, mock_app_cls, mock_session, create_mock_skill
    ):
        """Test that _get_skill_selection handles EOFError."""
        handler = SkillsHandler(mock_session)
        skills = [create_mock_skill("skill1")]

        mock_app = AsyncMock()
        mock_app.run_async = AsyncMock(side_effect=EOFError())
        mock_app_cls.return_value = mock_app

        await handler._get_skill_selection(skills)

    def test_format_skill_list_formats_correctly(self, create_mock_skill):
        """Test that _format_skill_list formats skills correctly."""
        skills = [create_mock_skill("skill1"), create_mock_skill("skill2")]

        formatted = SkillsHandler._format_skill_list(skills, 0, set(), 0, 10)

        assert formatted is not None

    def test_format_skill_list_with_expanded(self, create_mock_skill):
        """Test that _format_skill_list shows expanded description."""
        skills = [create_mock_skill("skill1"), create_mock_skill("skill2")]
        expanded_indices = {0}

        formatted = SkillsHandler._format_skill_list(skills, 0, expanded_indices, 0, 10)

        assert formatted is not None

    def test_format_skill_list_with_scrolling(self, create_mock_skill):
        """Test that _format_skill_list handles scrolling window."""
        skills = [create_mock_skill(f"skill{i}") for i in range(15)]

        formatted = SkillsHandler._format_skill_list(skills, 5, set(), 3, 10)

        assert formatted is not None

    @pytest.mark.asyncio
    async def test_handle_with_exception(self, mock_session, create_mock_skill):
        """Test that handle handles exceptions gracefully."""
        handler = SkillsHandler(mock_session)
        skills = [create_mock_skill("skill1")]

        with patch.object(
            handler, "_get_skill_selection", side_effect=Exception("Test error")
        ):
            with patch("src.cli.handlers.skills.console") as mock_console:
                with patch("src.cli.handlers.skills.logger") as mock_logger:
                    await handler.handle(skills)
                    # Verify error message was printed
                    mock_console.print_error.assert_called_once()
                    # Verify exception was logged
                    mock_logger.debug.assert_called_once()
