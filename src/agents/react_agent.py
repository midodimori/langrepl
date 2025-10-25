from collections.abc import Sequence
from typing import (
    Any,
    Literal,
    cast,
)

from langchain_core.language_models import (
    BaseChatModel,
)
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import (
    Runnable,
    RunnableConfig,
)
from langchain_core.tools import BaseTool
from langgraph._internal._runnable import RunnableCallable
from langgraph.errors import ErrorCode, create_error_message
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt.tool_node import ToolCall, ToolNode
from langgraph.store.base import BaseStore
from langgraph.types import Command, Send

from src.agents import StateSchema, StateSchemaType
from src.state.base import BaseState
from src.tools.internal.memory import read_memory_file
from src.utils.compression import calculate_message_tokens
from src.utils.cost import calculate_cost

PROMPT_RUNNABLE_NAME = "Prompt"


class CompressingToolNode(ToolNode):
    """ToolNode that compresses large outputs to virtual filesystem."""

    def __init__(
        self,
        tools: Sequence[BaseTool],
        model: BaseChatModel,
        **kwargs: Any,
    ) -> None:
        super().__init__(tools, **kwargs)
        self.model = model

    async def _arun_one(  # type: ignore[override]
        self,
        call: ToolCall,
        input_type: Literal["list", "dict", "tool_calls"],
        config: RunnableConfig,
    ) -> ToolMessage | Command:
        # Execute the tool normally
        result = await super()._arun_one(call, input_type, config)

        # If result is a Command, pass it through without compression
        if isinstance(result, Command):
            return result

        # Now we know it's a ToolMessage
        tool_msg = cast(ToolMessage, result)

        # Skip compression if disabled or error message
        if getattr(tool_msg, "status", None) == "error" or getattr(
            tool_msg, "is_error", False
        ):
            return tool_msg

        # Skip compression for read_memory_file - it's retrieving compressed content
        if tool_msg.name == read_memory_file.name:
            return tool_msg

        # Get max_tokens from config
        max_tokens = config.get("configurable", {}).get("tool_output_max_tokens")
        if not max_tokens:
            return tool_msg

        # Check if content is string and exceeds token limit
        content = tool_msg.content
        if not isinstance(content, str) or not content.strip():
            return tool_msg

        token_count = calculate_message_tokens(
            [HumanMessage(content=content)], self.model
        )

        if token_count > max_tokens:
            # Store in virtual filesystem
            file_id = f"tool_output_{tool_msg.tool_call_id}.txt"

            # Replace with reference message
            ref_content = (
                f"Tool output too large ({token_count} tokens), "
                f"stored in virtual file: {file_id}\n"
                f"Use read_memory_file('{file_id}') to access full content."
            )
            short_ref_content = f"Tool output too large ({token_count} tokens), result is stored in virtual file: {file_id}"

            compressed_msg = ToolMessage(
                id=tool_msg.id,
                name=tool_msg.name,
                content=ref_content,
                tool_call_id=tool_msg.tool_call_id,
                short_content=short_ref_content,
            )

            # Return Command to update both messages and files
            return Command(
                update={
                    "messages": [compressed_msg],
                    "files": {file_id: content},
                }
            )

        return tool_msg


def _get_prompt_runnable(prompt: SystemMessage) -> Runnable:
    prompt_runnable: Runnable = RunnableCallable(
        lambda state: [prompt] + state.messages,
        name=PROMPT_RUNNABLE_NAME,
    )
    return prompt_runnable


def _validate_chat_history(
    messages: Sequence[BaseMessage],
) -> None:
    """Validate that all tool calls in AIMessages have a corresponding ToolMessage."""
    all_tool_calls = [
        tool_call
        for message in messages
        if isinstance(message, AIMessage)
        for tool_call in message.tool_calls
    ]
    tool_call_ids_with_results = {
        message.tool_call_id for message in messages if isinstance(message, ToolMessage)
    }
    tool_calls_without_results = [
        tool_call
        for tool_call in all_tool_calls
        if tool_call["id"] not in tool_call_ids_with_results
    ]
    if not tool_calls_without_results:
        return

    error_message = create_error_message(
        message="Found AIMessages with tool_calls that do not have a corresponding ToolMessage. "
        f"Here are the first few of those tool calls: {tool_calls_without_results[:3]}.\n\n"
        "Every tool call (LLM requesting to call a tool) in the message history MUST have a corresponding ToolMessage "
        "(result of a tool invocation to return to the LLM) - this is required by most LLM providers.",
        error_code=ErrorCode.INVALID_CHAT_HISTORY,
    )
    raise ValueError(error_message)


def create_react_agent(
    model: BaseChatModel,
    tools: list[BaseTool],
    prompt: SystemMessage,
    state_schema: StateSchemaType | None = None,
    config_schema: type[Any] | None = None,
    store: BaseStore | None = None,
    name: str | None = None,
) -> CompiledStateGraph:

    final_state_schema: StateSchemaType = state_schema or BaseState

    # Check if read_memory_file is in the tools list to enable compression
    has_read_memory = read_memory_file in tools
    # Use CompressingToolNode if memory tools available, otherwise standard ToolNode
    tool_node: ToolNode | CompressingToolNode
    if has_read_memory:
        tool_node = CompressingToolNode([t for t in tools], model=model)
    else:
        tool_node = ToolNode([t for t in tools])

    tool_classes = list(tool_node.tools_by_name.values())
    model_with_tools = model.bind_tools(tool_classes)  # type: ignore[assignment]
    static_model: Runnable | None = _get_prompt_runnable(prompt) | model_with_tools
    should_return_direct = {t.name for t in tool_classes if t.return_direct}

    def _are_more_steps_needed(state: StateSchema, response: BaseMessage) -> bool:
        has_tool_calls = isinstance(response, AIMessage) and response.tool_calls
        all_tools_return_direct = (
            all(call["name"] in should_return_direct for call in response.tool_calls)
            if isinstance(response, AIMessage)
            else False
        )
        remaining_steps = state.remaining_steps
        if remaining_steps is not None:
            if remaining_steps < 1 and all_tools_return_direct:
                return True
            elif remaining_steps < 2 and has_tool_calls:
                return True

        return False

    def _get_model_input_state(state: StateSchema) -> StateSchema:
        messages = state.messages
        error_msg = (
            f"Expected input to call_model to have 'messages' key, but got {state}"
        )

        if messages is None:
            raise ValueError(error_msg)

        _validate_chat_history(messages)
        state.messages = messages  # type: ignore

        return state

    # Define the function that calls the model

    async def acall_model(state: StateSchema, config: RunnableConfig) -> dict[str, Any]:
        try:
            model_input = _get_model_input_state(state)
            response = cast(AIMessage, await static_model.ainvoke(model_input, config))  # type: ignore[union-attr]

            # add agent name to the AIMessage
            response.name = name
            if _are_more_steps_needed(state, response):
                return {
                    "messages": [
                        AIMessage(
                            id=response.id,
                            content="Sorry, need more steps to process this request.",
                            is_error=True,
                        )
                    ]
                }

            # Extract usage metadata and update state
            result: dict[str, Any] = {"messages": [response]}
            usage_metadata = getattr(response, "usage_metadata", None)
            if usage_metadata:
                result["current_input_tokens"] = usage_metadata.get("input_tokens")
                result["current_output_tokens"] = usage_metadata.get("output_tokens")

                # Calculate cost if pricing available

                input_cost = config.get("configurable", {}).get("input_cost_per_mtok")
                output_cost = config.get("configurable", {}).get("output_cost_per_mtok")
                if input_cost is not None and output_cost is not None:
                    call_cost = calculate_cost(
                        usage_metadata.get("input_tokens", 0),
                        usage_metadata.get("output_tokens", 0),
                        input_cost,
                        output_cost,
                    )
                    current_total = state.total_cost
                    result["total_cost"] = (
                        call_cost
                        if current_total is None
                        else current_total + call_cost
                    )

            return result
        except Exception as e:
            error_message = AIMessage(
                name=name,
                content=f"Error: {type(e).__name__}: {e}",
                is_error=True,
            )
            return {"messages": [error_message]}

    # Define the function that determines whether to continue or not
    def should_continue(state: StateSchema) -> str | list[Send]:
        messages = state.messages
        last_message = messages[-1]
        # If there is no function call, then we finish
        if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
            return END
        # Otherwise if there is, we continue
        else:
            tool_calls = [
                tool_node.inject_tool_args(call, state, store)  # type: ignore[arg-type]
                for call in last_message.tool_calls
            ]
            return [Send("tools", [tool_call]) for tool_call in tool_calls]

    # Define a new graph
    workflow = StateGraph(state_schema=final_state_schema, context_schema=config_schema)

    # Define the agent node
    workflow.add_node(
        "agent",
        RunnableCallable(func=None, afunc=acall_model),
        input_schema=final_state_schema,
    )
    workflow.add_node("tools", tool_node)
    entrypoint = "agent"
    workflow.set_entry_point(entrypoint)

    agent_paths = ["tools", END]

    workflow.add_conditional_edges(
        "agent",
        should_continue,
        path_map=agent_paths,
    )

    def route_tool_responses(state: StateSchema) -> str:
        m = None
        for m in reversed(state.messages):
            if not isinstance(m, ToolMessage):
                break
            if m.name in should_return_direct or getattr(m, "return_direct", False):
                return END

        if isinstance(m, AIMessage) and m.tool_calls:
            if any(call["name"] in should_return_direct for call in m.tool_calls):
                return END

        return entrypoint

    workflow.add_conditional_edges(
        "tools", route_tool_responses, path_map=[entrypoint, END]
    )

    return workflow.compile(
        store=store,
        name=name,
    )
