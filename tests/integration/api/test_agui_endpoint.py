"""Integration tests for AG-UI endpoint."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def agui_env(temp_dir: Path):
    """Set environment variables for AG-UI server."""
    env = {
        "LANGREPL_WORKING_DIR": str(temp_dir),
        "LANGREPL_APPROVAL_MODE": "none",
    }
    with patch.dict(os.environ, env):
        yield temp_dir


@pytest.fixture
def mock_create_graph():
    """Mock initializer.create_graph to return a fake graph."""

    async def _create_graph(agent, model, working_dir):
        # Create a minimal mock graph that can be used by LangGraphAgent
        from unittest.mock import MagicMock

        graph = MagicMock()
        graph.aget_state = AsyncMock()

        state_mock = MagicMock()
        state_mock.values = {"messages": []}
        state_mock.tasks = []
        state_mock.next = ()
        state_mock.metadata = {"writes": {}}
        graph.aget_state.return_value = state_mock

        cleanup = AsyncMock()
        return graph, cleanup

    return _create_graph


@pytest.mark.integration
class TestAGUIHealthEndpoint:
    """Test the AG-UI health endpoint."""

    def test_health_endpoint(self, agui_env: Path, mock_create_graph):
        with patch("langrepl.api.route.agui.initializer") as mock_init:
            mock_init.create_graph = AsyncMock(side_effect=mock_create_graph)

            from langrepl.api.route.agui import app

            with TestClient(app) as client:
                response = client.get("/agent/health")
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "ok"
                assert "agent" in data
