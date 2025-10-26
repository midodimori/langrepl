"""Virtual file system tools for agent state management.

This module provides tools for managing a virtual filesystem stored in agent state,
enabling context offloading and information persistence across agent interactions.
"""

from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, ToolException, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from pydantic import BaseModel, Field

from src.state.base import BaseState
from src.utils.render import format_diff_rich, generate_diff


class EditOperation(BaseModel):
    """Represents a single edit operation to replace old content with new content."""

    old_content: str = Field(..., description="The content to be replaced")
    new_content: str = Field(..., description="The new content to replace with")


class EditMemoryFileInput(BaseModel):
    """Input schema for edit_memory_file."""

    file_path: str = Field(..., description="Path to the memory file to edit")
    edits: list[EditOperation] = Field(
        ..., description="List of edit operations to apply sequentially"
    )


@tool()
async def list_memory_files(
    state: Annotated[BaseState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> ToolMessage:
    """List all files in the virtual memory filesystem stored in agent state.

    Shows what files currently exist in agent memory. Use this to orient yourself before other memory file operations
    and maintain awareness of your memory file organization.
    """
    file_list = list(state.files.keys())

    if not file_list:
        content = "No files in memory"
        short_content = "No memory files"
    else:
        content = "\n".join(f"- {file}" for file in sorted(file_list))
        short_content = f"Listed {len(file_list)} memory file(s)"

    return ToolMessage(
        name=list_memory_files.name,
        content=content,
        tool_call_id=tool_call_id,
        short_content=short_content,
    )


@tool()
async def read_memory_file(
    file_path: str,
    state: Annotated[BaseState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    start_line: int = 0,
    limit: int = 500,
) -> ToolMessage:
    """Read memory file content from virtual filesystem with line-based pagination.

    Essential before making any edits to understand existing content. Always read a memory file before editing it.

    Args:
        file_path: Path to the file to read
        start_line: Starting line number (0-based)
        limit: Maximum number of lines to read (default: 500)
    """
    files = state.files
    if file_path not in files:
        raise ToolException(f"File '{file_path}' not found")

    content = files[file_path]
    if not content:
        raise ToolException("System reminder: File exists but has empty contents")

    all_lines = content.splitlines()
    total_lines = len(all_lines)

    # Validate bounds
    start_idx = max(0, start_line)
    end_idx = min(total_lines, start_idx + limit)

    # Get the requested lines
    selected_lines = all_lines[start_idx:end_idx]

    # Add line numbers to content (0-based)
    numbered_content = "\n".join(
        f"{i + start_idx:4d} - {line[:2000]}" for i, line in enumerate(selected_lines)
    )

    # Generate short content summary
    actual_end = start_idx + len(selected_lines) - 1 if selected_lines else start_idx
    short_content = (
        f"Read {start_idx}-{actual_end} of {total_lines} lines from {file_path}"
    )

    # Add summary at the end for LLM context
    lines_read = len(selected_lines)
    content_with_summary = f"{numbered_content}\n\n[{start_idx}-{actual_end}, {lines_read}/{total_lines} lines]"

    return ToolMessage(
        name=read_memory_file.name,
        content=content_with_summary,
        tool_call_id=tool_call_id,
        short_content=short_content,
    )


@tool()
async def write_memory_file(
    file_path: str,
    content: str,
    state: Annotated[BaseState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Create a new memory file or completely overwrite an existing memory file in the virtual filesystem.

    This tool creates new memory files or replaces entire memory file contents. Use for initial memory file creation
    or complete rewrites.
    Files are stored persistently in agent state.

    Args:
        file_path: Path where the file should be created/updated
        content: Content to write to the file
    """
    files = state.files
    old_content = files.get(file_path, "")
    files[file_path] = content

    # Generate diff for short_content
    diff_lines = generate_diff(old_content, content, context_lines=3)
    short_content = format_diff_rich(diff_lines)

    return Command(
        update={
            "files": files,
            "messages": [
                ToolMessage(
                    name=write_memory_file.name,
                    content=f"Memory file written: {file_path}",
                    tool_call_id=tool_call_id,
                    short_content=short_content,
                )
            ],
        }
    )


@tool(args_schema=EditMemoryFileInput)
async def edit_memory_file(
    file_path: str,
    edits: list[EditOperation],
    state: Annotated[BaseState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Edit a memory file by replacing old content with new content.

    This tool makes targeted edits to existing memory files using exact string matching.
    Always read the memory file first before editing to ensure you have the exact content to match.

    Args:
        file_path: Path to the memory file to edit
        edits: List of edit operations to apply sequentially
    """
    files = state.files
    if file_path not in files:
        raise ToolException(f"File '{file_path}' not found")

    current_content = files[file_path]

    # Validate all old_content strings exist before making any changes
    for edit in edits:
        if edit.old_content not in current_content:
            raise ToolException(f"Old content not found in file: {file_path}")

    # Apply all replacements sequentially
    updated_content = current_content
    for edit in edits:
        updated_content = updated_content.replace(edit.old_content, edit.new_content)

    files[file_path] = updated_content

    # Generate diff for each edit section separately
    all_diff_sections = []
    for edit in edits:
        diff_lines = generate_diff(
            edit.old_content,
            edit.new_content,
            context_lines=3,
            full_content=current_content,
        )
        all_diff_sections.append(diff_lines)

    # Combine all diff sections with separator
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
                    tool_call_id=tool_call_id,
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
