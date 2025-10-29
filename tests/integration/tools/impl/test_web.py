"""Integration tests for web tools."""

from pathlib import Path
from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.tools.impl.web import fetch_web_content


@pytest.mark.asyncio
async def test_fetch_web_content(create_test_graph, temp_dir: Path):
    """Test fetching web content through the graph."""
    app = create_test_graph([fetch_web_content], temp_dir)

    # Mock trafilatura functions to avoid actual network call
    with (
        patch("src.tools.impl.web.trafilatura.fetch_url") as mock_fetch,
        patch("src.tools.impl.web.trafilatura.extract") as mock_extract,
    ):
        mock_fetch.return_value = (
            "<html><body><h1>Test Page</h1><p>Content</p></body></html>"
        )
        mock_extract.return_value = "# Test Page\n\nContent"

        initial_state = {
            "messages": [
                HumanMessage(content="Fetch web page"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "id": "call_1",
                            "name": "fetch_web_content",
                            "args": {"url": "https://example.com"},
                        }
                    ],
                ),
            ],
        }

        result = await app.ainvoke(
            initial_state,
            config={
                "configurable": {
                    "thread_id": "test",
                    "working_dir": str(temp_dir),
                    "approval_mode": "aggressive",
                }
            },
        )

        # Check that content was fetched
        tool_messages = [m for m in result["messages"] if m.type == "tool"]
        assert tool_messages
        assert "Test Page" in tool_messages[0].content
        assert "Content" in tool_messages[0].content


@pytest.mark.asyncio
async def test_fetch_web_content_no_content(create_test_graph, temp_dir: Path):
    """Test fetching web content when extraction fails."""
    app = create_test_graph([fetch_web_content], temp_dir)

    # Mock trafilatura to return no content
    with (
        patch("src.tools.impl.web.trafilatura.fetch_url") as mock_fetch,
        patch("src.tools.impl.web.trafilatura.extract") as mock_extract,
    ):
        mock_fetch.return_value = "<html><body></body></html>"
        mock_extract.return_value = None

        initial_state = {
            "messages": [
                HumanMessage(content="Fetch empty page"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "id": "call_1",
                            "name": "fetch_web_content",
                            "args": {"url": "https://example.com"},
                        }
                    ],
                ),
            ],
        }

        result = await app.ainvoke(
            initial_state,
            config={
                "configurable": {
                    "thread_id": "test",
                    "working_dir": str(temp_dir),
                    "approval_mode": "aggressive",
                }
            },
        )

        # Check that error message is returned
        tool_messages = [m for m in result["messages"] if m.type == "tool"]
        assert tool_messages
        assert "No main content could be extracted" in tool_messages[0].content


@pytest.mark.asyncio
async def test_fetch_web_content_network_error(create_test_graph, temp_dir: Path):
    """Test fetching web content with network error."""
    app = create_test_graph([fetch_web_content], temp_dir)

    # Mock trafilatura to raise exception
    with patch("src.tools.impl.web.trafilatura.fetch_url") as mock_fetch:
        mock_fetch.return_value = None

        initial_state = {
            "messages": [
                HumanMessage(content="Fetch unreachable page"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "id": "call_1",
                            "name": "fetch_web_content",
                            "args": {"url": "https://invalid-domain-xyz.com"},
                        }
                    ],
                ),
            ],
        }

        result = await app.ainvoke(
            initial_state,
            config={
                "configurable": {
                    "thread_id": "test",
                    "working_dir": str(temp_dir),
                    "approval_mode": "aggressive",
                }
            },
        )

        # Check that error is handled
        tool_messages = [m for m in result["messages"] if m.type == "tool"]
        assert tool_messages
