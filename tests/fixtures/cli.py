"""CLI-related test fixtures."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from prompt_toolkit.history import InMemoryHistory

from src.core.config import ApprovalMode


@pytest.fixture
def mock_context(temp_dir):
    """Create a mock CLI context for testing."""
    from src.cli.core.context import Context

    return Context(
        agent="test-agent",
        model="test-model",
        thread_id=str(uuid.uuid4()),
        working_dir=temp_dir,
        approval_mode=ApprovalMode.SEMI_ACTIVE,
        recursion_limit=25,
        context_window=100000,
        input_cost_per_mtok=1.0,
        output_cost_per_mtok=2.0,
    )


@pytest.fixture
def mock_session(mock_context, mock_renderer, mock_graph):
    """Create a mock CLI session for testing."""
    session = MagicMock()
    session.start = AsyncMock()
    session.send = AsyncMock(return_value=0)
    session.needs_reload = False
    session.running = True
    session.context = mock_context
    session.renderer = mock_renderer
    session.graph = mock_graph
    session.update_context = MagicMock()
    session.prefilled_text = ""
    session.prefilled_reference_mapping = {}
    session.command_dispatcher = MagicMock()
    session.command_dispatcher.resume_handler = MagicMock()
    session.command_dispatcher.resume_handler.handle = AsyncMock()
    return session


@pytest.fixture
def mock_prompt_session():
    """Create a mock prompt session for testing."""
    session = MagicMock()
    session.history = InMemoryHistory()
    session.prompt_async = AsyncMock(return_value="test input")
    return session


@pytest.fixture
def mock_renderer():
    """Create a mock renderer for testing."""
    from src.cli.ui.renderer import Renderer

    renderer = MagicMock(spec=Renderer)
    renderer.render_message = MagicMock()
    renderer.render_user_message = MagicMock()
    renderer.render_assistant_message = MagicMock()
    renderer.render_tool_message = MagicMock()
    renderer.show_welcome = MagicMock()
    renderer.render_help = MagicMock()
    renderer.render_graph = MagicMock()
    return renderer


async def _empty_async_iter():
    """Empty async iterator for mock completions."""
    return
    yield  # noqa: unreachable


@pytest.fixture
def mock_completer():
    """Create a mock completer router for testing."""
    from src.cli.completers.router import CompleterRouter

    completer = MagicMock(spec=CompleterRouter)
    completer.get_completions_async = MagicMock(
        side_effect=lambda *_: _empty_async_iter()
    )
    return completer


@pytest.fixture
def mock_app_args(temp_dir):
    """Create default mock args for CLI application tests."""
    return MagicMock(
        agent="test-agent",
        model="test-model",
        resume=False,
        message=None,
        working_dir=str(temp_dir),
        approval_mode=ApprovalMode.SEMI_ACTIVE,
        timer=False,
        server=False,
    )
