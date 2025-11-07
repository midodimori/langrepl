"""Virtual file system tools for agent state management.

This module provides tools for managing a virtual filesystem stored in agent state,
enabling context offloading and information persistence across agent interactions.
"""

from langchain.tools import ToolRuntime, tool
from langchain_core.messages import ToolMessage
from langchain_core.tools import ToolException
from langgraph.types import Command
from pydantic import BaseModel, Field

from src.agents.state import AgentState
from src.utils.render import format_diff_rich, generate_diff


class EditOperation(BaseModel):
    """Represents a single edit operation to replace old content with new content."""

    old_content: str = Field(..., description="The content to be replaced")
    new_content: str = Field(..., description="The new content to replace with")


@tool()
async def list_memory_files(
    runtime: ToolRuntime[None, AgentState],
) -> ToolMessage:
    """
    List filenames stored in the agent's in-memory virtual filesystem.
    
    Returns:
        ToolMessage: Message with `content` set to either "No files in memory" or a newline-separated bullet list of filenames, and `short_content` summarizing the result.
    """
    file_list = list(runtime.state["files"].keys())

    if not file_list:
        content = "No files in memory"
        short_content = "No memory files"
    else:
        content = "\n".join(f"- {file}" for file in sorted(file_list))
        short_content = f"Listed {len(file_list)} memory file(s)"

    return ToolMessage(
        name=list_memory_files.name,
        content=content,
        tool_call_id=runtime.tool_call_id,
        short_content=short_content,
    )


@tool()
async def read_memory_file(
    file_path: str,
    runtime: ToolRuntime[None, AgentState],
    start_line: int = 0,
    limit: int = 500,
) -> ToolMessage:
    """
    Read a file from the in-memory virtual filesystem and return a paginated, numbered view of its lines.
    
    Parameters:
        file_path (str): Path of the memory file to read.
        start_line (int): Zero-based index of the first line to return.
        limit (int): Maximum number of lines to return.
    
    Returns:
        ToolMessage: Message whose `content` contains the selected lines numbered and truncated where necessary,
                     followed by a bracketed summary "[start-end, lines_read/total_lines]". The message's `short_content`
                     summarizes the line range and total lines (e.g., "Read 0-9 of 42 lines from /path").
    
    Raises:
        ToolException: If the specified file does not exist or if the file exists but is empty.
    """
    files = runtime.state["files"]
    if file_path not in files:
        raise ToolException(f"File '{file_path}' not found")

    content = files[file_path]
    if not content:
        raise ToolException("System reminder: File exists but has empty contents")

    all_lines = content.splitlines()
    total_lines = len(all_lines)

    start_idx = max(0, start_line)
    end_idx = min(total_lines, start_idx + limit)

    selected_lines = all_lines[start_idx:end_idx]

    numbered_content = "\n".join(
        f"{i + start_idx:4d} - {line[:2000]}" for i, line in enumerate(selected_lines)
    )

    actual_end = start_idx + len(selected_lines) - 1 if selected_lines else start_idx
    short_content = (
        f"Read {start_idx}-{actual_end} of {total_lines} lines from {file_path}"
    )

    lines_read = len(selected_lines)
    content_with_summary = f"{numbered_content}\n\n[{start_idx}-{actual_end}, {lines_read}/{total_lines} lines]"

    return ToolMessage(
        name=read_memory_file.name,
        content=content_with_summary,
        tool_call_id=runtime.tool_call_id,
        short_content=short_content,
    )


@tool()
async def write_memory_file(
    file_path: str,
    content: str,
    runtime: ToolRuntime[None, AgentState],
) -> Command:
    """
    Create or overwrite a memory file in the agent's in-memory virtual filesystem.
    
    Updates the runtime's "files" mapping with the provided content and returns a Command describing the state update and a ToolMessage that summarizes the write and includes a rich diff of the change.
    
    Parameters:
        file_path (str): Destination path of the memory file to create or overwrite.
        content (str): Full content to store at `file_path`.
    
    Returns:
        Command: A command whose `update` contains the updated `files` mapping and a `messages` list with a ToolMessage summarizing the write and containing a formatted diff in `short_content`.
    """
    files = runtime.state["files"].copy()
    old_content = files.get(file_path, "")
    files[file_path] = content

    diff_lines = generate_diff(old_content, content, context_lines=3)
    short_content = format_diff_rich(diff_lines)

    return Command(
        update={
            "files": files,
            "messages": [
                ToolMessage(
                    name=write_memory_file.name,
                    content=f"Memory file written: {file_path}",
                    tool_call_id=runtime.tool_call_id,
                    short_content=short_content,
                )
            ],
        }
    )


@tool()
async def edit_memory_file(
    file_path: str,
    edits: list[EditOperation],
    runtime: ToolRuntime[None, AgentState],
) -> Command:
    """
    Apply a sequence of exact-match replacement edits to an existing in-memory file.
    
    Each EditOperation is applied sequentially by replacing its `old_content` with `new_content` in the file's content. The function updates runtime.state["files"] with the modified content and returns a Command containing the updated files mapping and a ToolMessage summarizing the edit with a combined diff.
    
    Parameters:
        file_path (str): Path of the memory file to edit.
        edits (list[EditOperation]): Edit operations applied in order; each `old_content` must match a substring of the file at the time of validation.
    
    Raises:
        ToolException: If the specified file does not exist or any edit's `old_content` is not found in the current file content.
    
    Returns:
        Command: Contains an `update` mapping with the new `files` state and `messages` including a ToolMessage summarizing the edit and a rich diff in `short_content`.
    """
    files = runtime.state["files"].copy()
    if file_path not in files:
        raise ToolException(f"File '{file_path}' not found")

    current_content = files[file_path]

    for edit in edits:
        if edit.old_content not in current_content:
            raise ToolException(f"Old content not found in file: {file_path}")

    updated_content = current_content
    for edit in edits:
        updated_content = updated_content.replace(edit.old_content, edit.new_content)

    files[file_path] = updated_content

    all_diff_sections = []
    for edit in edits:
        diff_lines = generate_diff(
            edit.old_content,
            edit.new_content,
            context_lines=3,
            full_content=current_content,
        )
        all_diff_sections.append(diff_lines)

    combined_diff = []
    for i, diff_section in enumerate(all_diff_sections):
        if i > 0:
            combined_diff.append("     ...")
        combined_diff.extend(diff_section)

    short_content = format_diff_rich(combined_diff)

    return Command(
        update={
            "files": files,
            "messages": [
                ToolMessage(
                    name=edit_memory_file.name,
                    content=f"Memory file edited: {file_path}",
                    tool_call_id=runtime.tool_call_id,
                    short_content=short_content,
                )
            ],
        }
    )


MEMORY_TOOLS = [
    write_memory_file,
    read_memory_file,
    list_memory_files,
    edit_memory_file,
]