"""Middleware for compressing large tool outputs to virtual filesystem."""

from collections.abc import Awaitable, Callable

from langchain.agents.middleware import AgentMiddleware
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.types import Command

from src.agents import AgentState
from src.agents.context import AgentContext
from src.tools.internal.memory import read_memory_file
from src.utils.compression import calculate_message_tokens


class CompressToolOutputMiddleware(AgentMiddleware[AgentState, AgentContext]):
    """Middleware to compress large tool outputs to virtual filesystem.

    When tool output exceeds token limit:
    1. Stores full content in state.files
    2. Replaces message content with reference
    3. Agent can use read_memory_file() to access full content
    """

    def __init__(self, model: BaseChatModel):
        """
        Initialize the middleware with the language model used for token calculations and compression decisions.
        
        Parameters:
            model (BaseChatModel): Language model used to compute message token counts and drive compression logic.
        """
        super().__init__()
        self.model = model

    def _compress_if_needed(
        self, tool_msg: ToolMessage, request: ToolCallRequest
    ) -> ToolMessage | Command:
        """
        Decide whether a tool message should be replaced with a reference to a stored file when its content exceeds a configured token limit.
        
        If compression is triggered, returns a Command that updates the messages to a compressed reference and writes the full content into the virtual filesystem under the key "tool_output_{tool_call_id}.txt". Compression is skipped for tool messages that represent errors or for messages from the read_memory_file tool. The token limit is taken from request.runtime.context.tool_output_max_tokens; if that value is missing or the message content is not a non-empty string, the original ToolMessage is returned unchanged.
        
        Parameters:
            tool_msg (ToolMessage): The tool result message to evaluate for compression.
            request (ToolCallRequest): The original tool call request whose runtime context may contain token limit configuration.
        
        Returns:
            ToolMessage | Command: The original ToolMessage when no compression is needed, or a Command that updates the message to a reference and stores the full content when compression is applied.
        """

        # Skip compression for errors
        if getattr(tool_msg, "status", None) == "error" or getattr(
            tool_msg, "is_error", False
        ):

            return tool_msg

        # Skip compression for read_memory_file (retrieving compressed content)
        if tool_msg.name == read_memory_file.name:

            return tool_msg

        # Get max_tokens from context
        max_tokens = (
            request.runtime.context.tool_output_max_tokens
            if request.runtime.context
            and hasattr(request.runtime.context, "tool_output_max_tokens")
            else None
        )

        if not max_tokens:
            return tool_msg

        # Check if content exceeds token limit
        content = tool_msg.content
        if not isinstance(content, str) or not content.strip():

            return tool_msg

        token_count = calculate_message_tokens(
            [HumanMessage(content=content)], self.model
        )

        if token_count > max_tokens:
            file_id = f"tool_output_{tool_msg.tool_call_id}.txt"

            ref_content = (
                f"Tool output too large ({token_count} tokens), "
                f"stored in virtual file: {file_id}\n"
                f"Use read_memory_file('{file_id}') to access full content."
            )
            short_ref_content = (
                f"Tool output too large ({token_count} tokens), "
                f"result is stored in virtual file: {file_id}"
            )

            compressed_msg = ToolMessage(
                id=tool_msg.id,
                name=tool_msg.name,
                content=ref_content,
                tool_call_id=tool_msg.tool_call_id,
                short_content=short_ref_content,
            )

            # Return Command to update both messages and files

            cmd = Command(
                update={
                    "messages": [compressed_msg],
                    "files": {file_id: content},
                }
            )

            return cmd

        return tool_msg

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        """
        Invoke the next tool-call handler and apply compression to its ToolMessage result when needed.
        
        Calls the provided handler with the given request, returns Commands unchanged, and passes ToolMessage results to _compress_if_needed which may return a modified ToolMessage or a Command that updates state and stores large outputs. Any other return value from the handler is returned as-is.
        
        Parameters:
            request (ToolCallRequest): The tool call request context.
            handler (Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]]): The next handler to invoke; receives the same request.
        
        Returns:
            ToolMessage | Command: The original or compressed ToolMessage, a Command to update state and persist files, or any other handler return value unchanged.
        """
        result = await handler(request)

        # If handler returned a Command, pass it through (tool already updated state)
        if isinstance(result, Command):

            return result

        # If handler returned ToolMessage, check if compression needed
        if isinstance(result, ToolMessage):
            return self._compress_if_needed(result, request)

        # Handler returned something else (shouldn't happen), pass through

        return result