from typing import Annotated, Literal, TypedDict

from langchain.agents import AgentState as BaseAgentState


class Todo(TypedDict):
    """Todo to track."""

    content: str
    status: Literal["pending", "in_progress", "completed"]


def file_reducer(
    left: dict[str, str] | None, right: dict[str, str] | None
) -> dict[str, str]:
    """Merge two file dictionaries, with right taking precedence."""
    if left is None:
        return right or {}
    elif right is None:
        return left
    else:
        return {**left, **right}


def add_reducer(left: int | None, right: int | None) -> int:
    """Add two integers, treating None as 0."""
    return (left or 0) + (right or 0)


def replace_reducer(left: int | None, right: int | None) -> int:
    """Replace with new value, treating None as 0."""
    return right if right is not None else (left or 0)


def sum_reducer(left: float | None, right: float | None) -> float:
    """Sum two floats, treating None as 0.0."""
    return (left or 0.0) + (right or 0.0)


class AgentState(BaseAgentState):
    """Agent state for LangChain v1 agents using create_agent."""

    todos: list[Todo] | None
    files: Annotated[dict[str, str] | None, file_reducer]
    current_input_tokens: Annotated[int | None, replace_reducer]
    current_output_tokens: Annotated[int | None, add_reducer]
    total_cost: Annotated[float | None, sum_reducer]
