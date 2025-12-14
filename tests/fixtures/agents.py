"""Agent-related test fixtures."""

from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

from src.configs import AgentConfig, LLMConfig, LLMProvider
from src.core.settings import LLMSettings


@pytest.fixture
def mock_llm_config():
    """Create a mock LLM config for testing."""
    return LLMConfig(
        alias="test-model",
        provider=LLMProvider.ANTHROPIC,
        model="claude-3-5-sonnet-20241022",
        max_tokens=4096,
        temperature=0.7,
        context_window=100000,
        input_cost_per_mtok=1.0,
        output_cost_per_mtok=2.0,
    )


@pytest.fixture
def mock_llm_settings():
    """Create a mock LLM settings for testing."""
    return LLMSettings(
        http_proxy=SecretStr(""),
        https_proxy=SecretStr(""),
    )


@pytest.fixture
def mock_agent_config(mock_llm_config, mock_checkpointer_config):
    """Create a mock agent config for testing."""
    return AgentConfig(
        name="test-agent",
        llm=mock_llm_config,
        checkpointer=mock_checkpointer_config,
        prompt="Test prompt",
        recursion_limit=25,
    )


@pytest.fixture
def mock_agents_config(mock_agent_config):
    """Create a mock agents config wrapper for testing."""
    config = MagicMock()
    config.agents = [mock_agent_config]
    return config


@pytest.fixture
def create_mock_tool():
    """Factory fixture for creating mock tools."""
    from typing import cast
    from unittest.mock import MagicMock

    from langchain_core.tools import BaseTool
    from pydantic import BaseModel

    class MockToolArgs(BaseModel):
        pass

    def _create(name: str) -> BaseTool:
        """Create a mock tool with proper typing."""
        mock = MagicMock(spec=BaseTool)
        mock.name = name
        mock.description = f"Mock tool {name}"
        mock.args_schema = MockToolArgs
        mock.tool_call_schema = MockToolArgs
        mock.handle_tool_error = False
        mock.metadata = None
        # Add func with __module__ for sandbox middleware compatibility
        mock_func = MagicMock()
        mock_func.__module__ = "tests.mock_tools"
        mock.func = mock_func
        mock.coroutine = None
        return cast(BaseTool, mock)

    return _create


@pytest.fixture
def agent_context(temp_dir):
    """Create AgentContext for tests."""
    from src.agents.context import AgentContext
    from src.configs import ApprovalMode

    return AgentContext(
        approval_mode=ApprovalMode.AGGRESSIVE,
        working_dir=temp_dir,
    )
