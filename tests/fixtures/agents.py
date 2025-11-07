"""Agent-related test fixtures."""

from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import SecretStr

from src.core.config import AgentConfig, LLMConfig, LLMProvider
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
def mock_llms_config(mock_llm_config):
    """Create a mock LLMs config wrapper for testing."""
    config = MagicMock()
    config.llms = [mock_llm_config]
    return config


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
def sample_messages():
    """Create sample messages for testing."""
    return [
        HumanMessage(content="Hello", id="msg_1"),
        AIMessage(content="Hi there!", id="msg_2"),
        HumanMessage(content="How are you?", id="msg_3"),
        AIMessage(content="I'm doing well!", id="msg_4"),
    ]


@pytest.fixture
def tool_call_messages():
    """Create messages with tool calls for testing."""
    from langchain_core.messages import ToolMessage

    return {
        "single_resolved": [
            HumanMessage(content="test", id="msg_1"),
            AIMessage(
                content="",
                tool_calls=[{"id": "call_123", "name": "tool1", "args": {}}],
                id="msg_2",
            ),
            ToolMessage(content="result", tool_call_id="call_123", id="msg_3"),
        ],
        "single_unresolved": [
            HumanMessage(content="test", id="msg_1"),
            AIMessage(
                content="",
                tool_calls=[{"id": "call_123", "name": "tool1", "args": {}}],
                id="msg_2",
            ),
        ],
        "multiple_resolved": [
            HumanMessage(content="test", id="msg_1"),
            AIMessage(
                content="",
                tool_calls=[
                    {"id": "call_1", "name": "tool1", "args": {}},
                    {"id": "call_2", "name": "tool2", "args": {}},
                ],
                id="msg_2",
            ),
            ToolMessage(content="result1", tool_call_id="call_1", id="msg_3"),
            ToolMessage(content="result2", tool_call_id="call_2", id="msg_4"),
        ],
        "multiple_partial": [
            HumanMessage(content="test", id="msg_1"),
            AIMessage(
                content="",
                tool_calls=[
                    {"id": "call_1", "name": "tool1", "args": {}},
                    {"id": "call_2", "name": "tool2", "args": {}},
                ],
                id="msg_2",
            ),
            ToolMessage(content="result1", tool_call_id="call_1", id="msg_3"),
        ],
    }


@pytest.fixture
def create_mock_tool():
    """
    Provide a factory that creates typed mock BaseTool instances for tests.
    
    The returned callable accepts a single `name` argument and produces a BaseTool-like object with:
    - `name`: set to the provided name
    - `description`: "Mock tool {name}"
    - `args_schema`: a minimal Pydantic BaseModel used as the tool's args schema
    - `handle_tool_error`: set to False
    - `metadata`: set to None
    
    Returns:
        Callable[[str], BaseTool]: A factory function that constructs the described mock tool.
    """
    from typing import cast
    from unittest.mock import MagicMock

    from langchain_core.tools import BaseTool
    from pydantic import BaseModel

    class MockToolArgs(BaseModel):
        pass

    def _create(name: str) -> BaseTool:
        """
        Create a mock BaseTool configured for tests.
        
        Parameters:
            name (str): The tool name to assign to the mock.
        
        Returns:
            BaseTool: A MagicMock cast to `BaseTool` with `name`, `description`, `args_schema`, `handle_tool_error`, and `metadata` set for testing.
        """
        mock = MagicMock(spec=BaseTool)
        mock.name = name
        mock.description = f"Mock tool {name}"
        mock.args_schema = MockToolArgs
        mock.handle_tool_error = False
        mock.metadata = None
        return cast(BaseTool, mock)

    return _create


@pytest.fixture
def agent_context(temp_dir):
    """
    Create an AgentContext configured for tests with AGGRESSIVE approval mode.
    
    Parameters:
        temp_dir (str | pathlib.Path): Directory to use as the agent's working directory.
    
    Returns:
        AgentContext: An AgentContext instance with approval_mode set to ApprovalMode.AGGRESSIVE and working_dir set to `temp_dir`.
    """
    from src.agents.context import AgentContext
    from src.core.config import ApprovalMode

    return AgentContext(
        approval_mode=ApprovalMode.AGGRESSIVE,
        working_dir=temp_dir,
    )