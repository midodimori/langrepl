"""Tests for CLI context module."""

import uuid
from unittest.mock import patch

import pytest

from src.cli.core.context import Context
from src.core.config import ApprovalMode


def _configure_initializer_mock(target, source):
    """Copy initializer async functions from fixture onto patched object."""
    for attr in ("load_agent_config", "get_threads", "load_llm_config"):
        setattr(target, attr, getattr(source, attr))


class TestContextCreate:
    """Tests for Context.create() classmethod."""

    @pytest.mark.asyncio
    @patch("src.cli.core.context.initializer")
    async def test_create_without_resume_generates_new_thread_id(
        self,
        mock_initializer_patch,
        temp_dir,
        mock_initializer,
    ):
        """Test that create() generates new thread_id when resume=False."""
        _configure_initializer_mock(mock_initializer_patch, mock_initializer)
        context = await Context.create(
            agent="test-agent",
            model=None,
            approval_mode=None,
            resume=False,
            working_dir=temp_dir,
        )

        assert context.thread_id is not None
        assert len(context.thread_id) == 36
        mock_initializer.get_threads.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.cli.core.context.initializer")
    async def test_create_with_resume_retrieves_latest_thread(
        self,
        mock_initializer_patch,
        temp_dir,
        mock_initializer,
    ):
        """Test that create() retrieves latest thread when resume=True."""
        existing_thread_id = str(uuid.uuid4())
        mock_initializer.get_threads.return_value = [
            {"thread_id": existing_thread_id, "timestamp": "2024-01-01T00:00:00"}
        ]

        _configure_initializer_mock(mock_initializer_patch, mock_initializer)
        context = await Context.create(
            agent="test-agent",
            model=None,
            approval_mode=None,
            resume=True,
            working_dir=temp_dir,
        )

        assert context.thread_id == existing_thread_id
        mock_initializer.get_threads.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.cli.core.context.initializer")
    async def test_create_with_resume_generates_thread_when_none_exist(
        self,
        mock_initializer_patch,
        temp_dir,
        mock_initializer,
    ):
        """Test that create() generates new thread when resume=True but no threads exist."""
        mock_initializer.get_threads.return_value = []

        _configure_initializer_mock(mock_initializer_patch, mock_initializer)
        context = await Context.create(
            agent="test-agent",
            model=None,
            approval_mode=None,
            resume=True,
            working_dir=temp_dir,
        )

        assert context.thread_id is not None
        assert len(context.thread_id) == 36
        mock_initializer.get_threads.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.cli.core.context.initializer")
    async def test_create_with_custom_model(
        self,
        mock_initializer_patch,
        temp_dir,
        mock_llm_config,
        mock_initializer,
    ):
        """Test that create() loads custom model config when specified."""
        _configure_initializer_mock(mock_initializer_patch, mock_initializer)
        context = await Context.create(
            agent="test-agent",
            model="custom-model",
            approval_mode=None,
            resume=False,
            working_dir=temp_dir,
        )

        assert context.model == "custom-model"
        mock_initializer.load_llm_config.assert_called_once_with(
            "custom-model", temp_dir
        )

    @pytest.mark.asyncio
    @patch("src.cli.core.context.initializer")
    async def test_create_without_custom_model_uses_agent_llm(
        self,
        mock_initializer_patch,
        temp_dir,
        mock_agent_config,
        mock_initializer,
    ):
        """Test that create() uses agent's default LLM when no model specified."""
        _configure_initializer_mock(mock_initializer_patch, mock_initializer)
        context = await Context.create(
            agent="test-agent",
            model=None,
            approval_mode=None,
            resume=False,
            working_dir=temp_dir,
        )

        assert context.model == mock_agent_config.llm.alias
        mock_initializer.load_llm_config.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.cli.core.context.initializer")
    async def test_create_with_custom_approval_mode(
        self,
        mock_initializer_patch,
        temp_dir,
        mock_initializer,
    ):
        """Test that create() sets custom approval mode when specified."""
        _configure_initializer_mock(mock_initializer_patch, mock_initializer)
        context = await Context.create(
            agent="test-agent",
            model=None,
            approval_mode=ApprovalMode.ACTIVE,
            resume=False,
            working_dir=temp_dir,
        )

        assert context.approval_mode == ApprovalMode.ACTIVE

    @pytest.mark.asyncio
    @patch("src.cli.core.context.initializer")
    async def test_create_without_approval_mode_defaults_to_semi_active(
        self,
        mock_initializer_patch,
        temp_dir,
        mock_initializer,
    ):
        """Test that create() defaults to SEMI_ACTIVE when no approval mode specified."""
        _configure_initializer_mock(mock_initializer_patch, mock_initializer)
        context = await Context.create(
            agent="test-agent",
            model=None,
            approval_mode=None,
            resume=False,
            working_dir=temp_dir,
        )

        assert context.approval_mode == ApprovalMode.SEMI_ACTIVE

    @pytest.mark.asyncio
    @patch("src.cli.core.context.initializer")
    async def test_create_populates_llm_config_fields(
        self,
        mock_initializer_patch,
        temp_dir,
        mock_llm_config,
        mock_initializer,
    ):
        """Test that create() populates context with LLM config fields."""
        _configure_initializer_mock(mock_initializer_patch, mock_initializer)
        context = await Context.create(
            agent="test-agent",
            model=None,
            approval_mode=None,
            resume=False,
            working_dir=temp_dir,
        )

        assert context.context_window == mock_llm_config.context_window
        assert context.input_cost_per_mtok == mock_llm_config.input_cost_per_mtok
        assert context.output_cost_per_mtok == mock_llm_config.output_cost_per_mtok

    @pytest.mark.asyncio
    @patch("src.cli.core.context.initializer")
    async def test_create_populates_agent_config_fields(
        self,
        mock_initializer_patch,
        temp_dir,
        mock_agent_config,
        mock_initializer,
    ):
        """Test that create() populates context with agent config fields."""
        _configure_initializer_mock(mock_initializer_patch, mock_initializer)
        context = await Context.create(
            agent="test-agent",
            model=None,
            approval_mode=None,
            resume=False,
            working_dir=temp_dir,
        )

        assert context.recursion_limit == mock_agent_config.recursion_limit
        assert (
            context.tool_output_max_tokens == mock_agent_config.tool_output_max_tokens
        )

    @pytest.mark.asyncio
    @patch("src.cli.core.context.initializer")
    async def test_create_with_none_agent_uses_default(
        self,
        mock_initializer_patch,
        temp_dir,
        mock_agent_config,
        mock_initializer,
    ):
        """Test that create() uses default agent when agent=None."""
        _configure_initializer_mock(mock_initializer_patch, mock_initializer)
        context = await Context.create(
            agent=None,
            model=None,
            approval_mode=None,
            resume=False,
            working_dir=temp_dir,
        )

        assert context.agent == mock_agent_config.name


class TestContextCycleApprovalMode:
    """Tests for Context.cycle_approval_mode() method."""

    def test_cycle_approval_mode_from_semi_active(self, mock_context):
        """Test cycling from SEMI_ACTIVE to ACTIVE."""
        mock_context.approval_mode = ApprovalMode.SEMI_ACTIVE

        result = mock_context.cycle_approval_mode()

        assert result == ApprovalMode.ACTIVE
        assert mock_context.approval_mode == ApprovalMode.ACTIVE

    def test_cycle_approval_mode_from_active(self, mock_context):
        """Test cycling from ACTIVE to AGGRESSIVE."""
        mock_context.approval_mode = ApprovalMode.ACTIVE

        result = mock_context.cycle_approval_mode()

        assert result == ApprovalMode.AGGRESSIVE
        assert mock_context.approval_mode == ApprovalMode.AGGRESSIVE

    def test_cycle_approval_mode_from_aggressive_wraps_around(self, mock_context):
        """Test cycling from AGGRESSIVE wraps around to SEMI_ACTIVE."""
        mock_context.approval_mode = ApprovalMode.AGGRESSIVE

        result = mock_context.cycle_approval_mode()

        assert result == ApprovalMode.SEMI_ACTIVE
        assert mock_context.approval_mode == ApprovalMode.SEMI_ACTIVE

    def test_cycle_approval_mode_multiple_cycles(self, mock_context):
        """Test cycling through all modes multiple times."""
        mock_context.approval_mode = ApprovalMode.SEMI_ACTIVE

        mock_context.cycle_approval_mode()
        assert mock_context.approval_mode == ApprovalMode.ACTIVE

        mock_context.cycle_approval_mode()
        assert mock_context.approval_mode == ApprovalMode.AGGRESSIVE

        mock_context.cycle_approval_mode()
        assert mock_context.approval_mode == ApprovalMode.SEMI_ACTIVE

        mock_context.cycle_approval_mode()
        assert mock_context.approval_mode == ApprovalMode.ACTIVE
