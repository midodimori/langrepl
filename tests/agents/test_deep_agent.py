from types import SimpleNamespace
from unittest.mock import MagicMock

from src.agents import deep_agent
from src.agents.deep_agent import create_deep_agent
from src.tools.subagents.task import SubAgent


def test_create_deep_agent_builds_model_via_provider(monkeypatch):
    llm_config = MagicMock()
    built_model = object()
    captured = {}

    def fake_provider(cfg):
        captured["cfg"] = cfg
        return built_model

    def fake_create_react_agent(model, **kwargs):
        captured["model"] = model
        captured["kwargs"] = kwargs
        return "graph"

    monkeypatch.setattr(deep_agent, "create_react_agent", fake_create_react_agent)

    graph = create_deep_agent(
        tools=[],
        prompt="prompt",
        llm_config=llm_config,
        model_provider=fake_provider,
    )

    assert graph == "graph"
    assert captured["cfg"] is llm_config
    assert captured["model"] is built_model
    assert captured["kwargs"]["tools"] == []


def test_create_deep_agent_passes_provider_to_task_tool(monkeypatch):
    llm_config = MagicMock()
    provider = MagicMock(return_value=object())
    captured = {}

    def fake_create_task_tool(subagents, model_provider, state_schema):
        captured["subagents"] = subagents
        captured["model_provider"] = model_provider
        captured["state_schema"] = state_schema
        return "task_tool"

    def fake_create_react_agent(model, tools, **kwargs):
        captured["model"] = model
        captured["tools"] = tools
        captured["kwargs"] = kwargs
        return "graph"

    monkeypatch.setattr(deep_agent, "create_task_tool", fake_create_task_tool)
    monkeypatch.setattr(deep_agent, "create_react_agent", fake_create_react_agent)

    subagent = SubAgent.model_construct(
        config=SimpleNamespace(
            name="helper", description="helper agent", llm=llm_config, tools=None
        ),
        prompt="sub prompt",
        tools=[],
        internal_tools=[],
    )

    graph = create_deep_agent(
        tools=[],
        prompt="prompt",
        llm_config=llm_config,
        model_provider=provider,
        subagents=[subagent],
        state_schema="state",  # type: ignore[arg-type]
    )

    assert graph == "graph"
    assert captured["model"] is provider.return_value
    assert captured["model_provider"] is provider
    assert captured["state_schema"] == "state"
    assert captured["subagents"] == [subagent]
    assert "task_tool" in captured["tools"]
