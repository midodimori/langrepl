"""Tests for TokenCostMiddleware."""

from unittest.mock import Mock

import pytest
from langchain_core.messages import AIMessage

from src.agents.context import AgentContext
from src.agents.state import AgentState
from src.core.config import ApprovalMode
from src.middleware.token_cost import TokenCostMiddleware


class TestTokenCostMiddleware:
    """Tests for TokenCostMiddleware class."""

    @pytest.mark.asyncio
    async def test_extracts_token_usage_from_ai_message(self, temp_dir):
        """Test that middleware extracts token usage from AI message."""
        middleware = TokenCostMiddleware()

        # Create AI message with usage metadata
        ai_message = AIMessage(
            content="test response",
            usage_metadata={
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150,
            },
        )

        state: AgentState = {
            "messages": [ai_message],
            "todos": None,
            "files": {},
            "current_input_tokens": None,
            "current_output_tokens": None,
            "total_cost": None,
        }

        runtime = Mock()
        runtime.context = AgentContext(
            approval_mode=ApprovalMode.SEMI_ACTIVE,
            working_dir=temp_dir,
            input_cost_per_mtok=1.0,
            output_cost_per_mtok=2.0,
        )

        result = await middleware.aafter_model(state, runtime)

        assert result is not None
        assert result["current_input_tokens"] == 100
        assert result["current_output_tokens"] == 50
        # Cost: (100/1M * 1.0) + (50/1M * 2.0) = 0.0001 + 0.0001 = 0.0002
        assert result["total_cost"] == pytest.approx(0.0002)

    @pytest.mark.asyncio
    async def test_returns_none_when_no_messages(self, temp_dir):
        """Test that middleware returns None when state has no messages."""
        middleware = TokenCostMiddleware()

        state: AgentState = {
            "messages": [],
            "todos": None,
            "files": {},
            "current_input_tokens": None,
            "current_output_tokens": None,
            "total_cost": None,
        }

        runtime = Mock()
        runtime.context = AgentContext(
            approval_mode=ApprovalMode.SEMI_ACTIVE,
            working_dir=temp_dir,
        )

        result = await middleware.aafter_model(state, runtime)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_usage_metadata(self, temp_dir):
        """Test that middleware returns None when message has no usage metadata."""
        middleware = TokenCostMiddleware()

        ai_message = Mock()
        ai_message.usage_metadata = None

        state: AgentState = {
            "messages": [ai_message],
            "todos": None,
            "files": {},
            "current_input_tokens": None,
            "current_output_tokens": None,
            "total_cost": None,
        }

        runtime = Mock()
        runtime.context = AgentContext(
            approval_mode=ApprovalMode.SEMI_ACTIVE,
            working_dir=temp_dir,
        )

        result = await middleware.aafter_model(state, runtime)

        assert result is None

    @pytest.mark.asyncio
    async def test_no_cost_calculation_when_pricing_not_available(self, temp_dir):
        """Test that cost is not calculated when pricing info is missing."""
        middleware = TokenCostMiddleware()

        ai_message = AIMessage(
            content="test response",
            usage_metadata={
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150,
            },
        )

        state: AgentState = {
            "messages": [ai_message],
            "todos": None,
            "files": {},
            "current_input_tokens": None,
            "current_output_tokens": None,
            "total_cost": None,
        }

        runtime = Mock()
        runtime.context = AgentContext(
            approval_mode=ApprovalMode.SEMI_ACTIVE,
            working_dir=temp_dir,
            input_cost_per_mtok=None,
            output_cost_per_mtok=None,
        )

        result = await middleware.aafter_model(state, runtime)

        assert result is not None
        assert result["current_input_tokens"] == 100
        assert result["current_output_tokens"] == 50
        assert "total_cost" not in result

    @pytest.mark.asyncio
    async def test_handles_partial_pricing_info(self, temp_dir):
        """Test that cost is not calculated when only partial pricing is available."""
        middleware = TokenCostMiddleware()

        ai_message = AIMessage(
            content="test response",
            usage_metadata={
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150,
            },
        )

        state: AgentState = {
            "messages": [ai_message],
            "todos": None,
            "files": {},
            "current_input_tokens": None,
            "current_output_tokens": None,
            "total_cost": None,
        }

        runtime = Mock()
        runtime.context = AgentContext(
            approval_mode=ApprovalMode.SEMI_ACTIVE,
            working_dir=temp_dir,
            input_cost_per_mtok=1.0,
            output_cost_per_mtok=None,  # Missing output cost
        )

        result = await middleware.aafter_model(state, runtime)

        assert result is not None
        assert result["current_input_tokens"] == 100
        assert result["current_output_tokens"] == 50
        assert "total_cost" not in result
