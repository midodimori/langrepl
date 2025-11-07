from typing import Annotated, Literal, TypedDict

from langchain.agents import AgentState as BaseAgentState


class Todo(TypedDict):
    """Todo to track."""

    content: str
    status: Literal["pending", "in_progress", "completed"]


def file_reducer(
    left: dict[str, str] | None, right: dict[str, str] | None
) -> dict[str, str]:
    """
    Merge two file mappings, with entries from the right mapping overriding those from the left.
    
    Parameters:
        left (dict[str, str] | None): Mapping of file path to file contents, or None.
        right (dict[str, str] | None): Mapping of file path to file contents, or None.
    
    Returns:
        dict[str, str]: Merged file mapping. If `left` is None returns `right` or an empty dict; if `right` is None returns `left`.
    """
    if left is None:
        return right or {}
    elif right is None:
        return left
    else:
        return {**left, **right}


def add_reducer(left: int | None, right: int | None) -> int:
    """
    Return the sum of two integers, treating None as zero.
    
    Parameters:
        left (int | None): Left addend; treated as 0 if None.
        right (int | None): Right addend; treated as 0 if None.
    
    Returns:
        int: Sum of the two addends with None treated as 0.
    """
    return (left or 0) + (right or 0)


def sum_reducer(left: float | None, right: float | None) -> float:
    """
    Sum two float values, treating `None` as 0.0.
    
    Returns:
        sum (float): The numeric sum of `left` and `right`, with `None` treated as 0.0.
    """
    return (left or 0.0) + (right or 0.0)


class AgentState(BaseAgentState):
    """Agent state for LangChain v1 agents using create_agent."""

    todos: list[Todo] | None
    files: Annotated[dict[str, str], file_reducer]
    current_input_tokens: Annotated[int | None, add_reducer]
    current_output_tokens: Annotated[int | None, add_reducer]
    total_cost: Annotated[float | None, sum_reducer]