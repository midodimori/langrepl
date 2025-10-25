from typing import Annotated, Literal, TypedDict

from langgraph.prebuilt.chat_agent_executor import AgentStatePydantic
from pydantic import ConfigDict, Field


class Todo(TypedDict):
    """Todo to track."""

    content: str
    status: Literal["pending", "in_progress", "completed"]


def file_reducer(l, r):
    if l is None:
        return r
    elif r is None:
        return l
    else:
        return {**l, **r}


class BaseState(AgentStatePydantic):
    todos: list[Todo] | None = None
    files: Annotated[dict[str, str], file_reducer] = Field(default_factory=dict)
    current_input_tokens: int | None = None
    current_output_tokens: int | None = None
    total_cost: float | None = None
    model_config = ConfigDict(extra="allow")
