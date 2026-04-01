"""Integration tests for AG-UI endpoint."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_create_graph():
    """Mock initializer.create_graph to return a fake graph."""

    async def _create_graph(agent, model, working_dir):
        from unittest.mock import MagicMock as MM

        graph = MM()
        graph.aget_state = AsyncMock()

        state_mock = MM()
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

    def test_health_endpoint(self, temp_dir: Path, mock_create_graph):
        mock_registry = MagicMock()
        mock_registry.ensure_config_dir = AsyncMock()
        mock_registry.load_agents = AsyncMock(
            return_value=MagicMock(
                agent_names=["test-agent"],
                get_agent_config=MagicMock(return_value=MagicMock(default=True)),
            )
        )

        with patch("langrepl.api.route.agui.initializer") as mock_init:
            mock_init.create_graph = AsyncMock(side_effect=mock_create_graph)
            mock_init.get_registry = MagicMock(return_value=mock_registry)

            from langrepl.api.route.agui import create_app

            app = create_app(working_dir=str(temp_dir), agent="test-agent")

            with TestClient(app) as client:
                response = client.get("/agent/test-agent/health")
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "ok"
                assert data["agent"]["name"] == "test-agent"

    def test_list_agents(self, temp_dir: Path, mock_create_graph):
        mock_registry = MagicMock()
        mock_registry.ensure_config_dir = AsyncMock()
        mock_registry.load_agents = AsyncMock(
            return_value=MagicMock(
                agent_names=["general"],
                get_agent_config=MagicMock(return_value=MagicMock(default=True)),
            )
        )

        with patch("langrepl.api.route.agui.initializer") as mock_init:
            mock_init.create_graph = AsyncMock(side_effect=mock_create_graph)
            mock_init.get_registry = MagicMock(return_value=mock_registry)

            from langrepl.api.route.agui import create_app

            app = create_app(working_dir=str(temp_dir), agent="general")

            with TestClient(app) as client:
                response = client.get("/agents")
                assert response.status_code == 200
                agents = response.json()
                assert len(agents) == 1
                assert agents[0]["name"] == "general"
                assert agents[0]["default"] is True
