import json
import shutil
from typing import Annotated

from json_repair import repair_json
from langchain.tools import ToolRuntime, tool
from langchain_core.messages import ToolMessage
from langchain_core.tools import ToolException
from pydantic import BaseModel, Field

from src.agents.context import AgentContext
from src.cli.theme import theme
from src.utils.matching import find_progressive_match, format_match_error
from src.utils.path import resolve_path
from src.utils.render import format_diff_rich, generate_diff
from src.utils.validators import json_safe_tool


class EditOperation(BaseModel):
    """Represents a single edit operation to replace old content with new content."""

    old_content: str = Field(..., description="The content to be replaced")
    new_content: str = Field(..., description="The new content to replace with")


class MoveOperation(BaseModel):
    """Represents a single file move operation."""

    source: str = Field(
        ..., description="Source file path (relative to working directory or absolute)"
    )
    destination: str = Field(
        ...,
        description="Destination file path (relative to working directory or absolute)",
    )


def _get_attr(obj: dict | BaseModel, attr: str, default: str = "") -> str:
    """Extract attribute from either dict or Pydantic model instance."""
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)


def _render_diff_args(args: dict, config: dict) -> str:
    """Render arguments with colored diff preview."""
    file_path = args.get("file_path", "")

    working_dir = config.get("configurable", {}).get("working_dir")
    full_content = None
    if working_dir and file_path:
        try:
            path = resolve_path(working_dir, file_path)
            if path.exists():
                full_content = path.read_text(encoding="utf-8")
        except Exception:
            pass

    edits = args.get("edits")
    if isinstance(edits, str):
        try:
            edits = json.loads(edits)
        except (json.JSONDecodeError, ValueError):
            try:
                edits = json.loads(repair_json(edits))
            except Exception:
                return f"[{theme.error_color}]Cannot parse edits (malformed JSON)[/{theme.error_color}]"

    if edits and isinstance(edits, list):
        sorted_edits = []
        for idx, edit in enumerate(edits):
            old_content = _get_attr(edit, "old_content")
            new_content = _get_attr(edit, "new_content")
            start_pos = float("inf")
            if full_content:
                found, start, _ = find_progressive_match(full_content, old_content)
                if found:
                    start_pos = start
            sorted_edits.append((start_pos, idx, old_content, new_content))

        # Keep original order for unmatched edits by using idx as secondary key
        sorted_edits.sort(key=lambda item: (item[0], item[1]))

        all_diff_sections = []
        for _, _, old_content, new_content in sorted_edits:
            diff_lines = generate_diff(
                old_content, new_content, context_lines=3, full_content=full_content
            )
            if diff_lines:
                all_diff_sections.append(diff_lines)

        combined_diff = []
        for i, diff_section in enumerate(all_diff_sections):
            if i > 0:
                combined_diff.append("     ...")
            combined_diff.extend(diff_section)

        diff_preview = format_diff_rich(combined_diff)
    else:
        old_content = ""
        new_content = args.get("content", "")

        diff_lines = generate_diff(
            old_content, new_content, context_lines=3, full_content=full_content
        )
        diff_preview = format_diff_rich(diff_lines)

    return (
        f"[{theme.info_color}]Path: {file_path}[/{theme.info_color}]\n{diff_preview}\n"
    )


@tool
async def read_file(
    runtime: ToolRuntime[AgentContext],
    file_path: str,
    start_line: int = 0,
    limit: int = 500,
) -> ToolMessage:
    """
    Use this tool to read the content of a file with line-based pagination.

    Args:
        file_path: Path to the file to read (relative to working directory or absolute)
        start_line: Starting line number (0-based) to read from (default: 0)
        limit: Maximum number of lines to read (default: 500)
    """
    context: AgentContext = runtime.context
    working_dir = str(context.working_dir)

    path = resolve_path(working_dir, file_path)

    with open(path, encoding="utf-8") as f:
        all_lines = f.readlines()

    total_lines = len(all_lines)

    start_idx = max(0, start_line)
    end_idx = min(total_lines, start_idx + limit)

    selected_lines = all_lines[start_idx:end_idx]

    numbered_content = "\n".join(
        f"{i + start_idx:4d} - {line.rstrip()}" for i, line in enumerate(selected_lines)
    )

    actual_end = start_idx + len(selected_lines) - 1 if selected_lines else start_idx
    short_content = (
        f"Read {start_idx}-{actual_end} of {total_lines} lines from {path.name}"
    )

    lines_read = len(selected_lines)
    content_with_summary = f"{numbered_content}\n\n[{start_idx}-{actual_end}, {lines_read}/{total_lines} lines]"

    return ToolMessage(
        name=read_file.name,
        content=content_with_summary,
        tool_call_id=runtime.tool_call_id,
        short_content=short_content,
    )


read_file.metadata = {
    "approval_config": {
        "name_only": True,
    }
}


@tool
async def write_file(
    file_path: str,
    content: str,
    runtime: ToolRuntime[AgentContext],
) -> ToolMessage:
    """
    Use this tool to create a new file with content. Only for files that don't exist yet.
    If the file already exists, use edit_file instead.

    Args:
        file_path: Path to the file to write (relative to working directory or absolute)
        content: Content to write to the file
    """
    context: AgentContext = runtime.context
    working_dir = str(context.working_dir)
    path = resolve_path(working_dir, file_path)

    if path.exists():
        raise ToolException(f"File already exists: {path}. Use edit_file instead.")

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    diff_lines = generate_diff("", content, context_lines=3)
    short_content = format_diff_rich(diff_lines)

    return ToolMessage(
        name=write_file.name,
        content=f"File written: {path}",
        tool_call_id=runtime.tool_call_id,
        short_content=short_content,
    )


write_file.metadata = {
    "approval_config": {
        "name_only": True,
        "render_args_fn": _render_diff_args,
    }
}


@json_safe_tool
async def edit_file(
    file_path: Annotated[
        str,
        Field(
            description="Path to the file to edit (relative to working directory or absolute)"
        ),
    ],
    edits: Annotated[
        list[EditOperation], Field(description="Edit operations to apply sequentially")
    ],
    runtime: ToolRuntime[AgentContext],
) -> ToolMessage:
    """Use this tool to edit a file by replacing old content with new content."""
    context: AgentContext = runtime.context
    working_dir = str(context.working_dir)
    path = resolve_path(working_dir, file_path)

    if not path.exists():
        raise ToolException(f"File does not exist: {path}")

    with open(path, encoding="utf-8") as f:
        current_content = f.read()

    matches = []
    for i, edit in enumerate(edits):
        found, start, end = find_progressive_match(current_content, edit.old_content)
        if not found:
            error_msg = format_match_error(
                str(path), i + 1, edit.old_content, current_content
            )
            raise ToolException(error_msg)
        matches.append((i, start, end, edit.new_content))

    # Check for overlapping ranges
    sorted_matches = sorted(matches, key=lambda m: m[1])  # Sort by start position
    for i in range(len(sorted_matches) - 1):
        curr_idx, curr_start, curr_end, _ = sorted_matches[i]
        next_idx, next_start, next_end, _ = sorted_matches[i + 1]
        if next_start < curr_end:
            raise ToolException(
                f"Overlapping edits detected in {path}: "
                f"edit #{curr_idx + 1} [{curr_start}:{curr_end}] overlaps with "
                f"edit #{next_idx + 1} [{next_start}:{next_end}]"
            )

    updated_content = current_content
    for _, start, end, new_content in sorted(matches, key=lambda m: m[1], reverse=True):
        updated_content = updated_content[:start] + new_content + updated_content[end:]

    with open(path, "w", encoding="utf-8") as f:
        f.write(updated_content)

    all_diff_sections = []
    for idx, _, _, _ in sorted_matches:
        edit = edits[idx]
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

    return ToolMessage(
        name=edit_file.name,
        content=f"File edited: {path}",
        tool_call_id=runtime.tool_call_id,
        short_content=short_content,
    )


edit_file.metadata = {
    "approval_config": {
        "name_only": True,
        "render_args_fn": _render_diff_args,
    }
}


@tool
async def create_dir(
    dir_path: str,
    runtime: ToolRuntime[AgentContext],
) -> str:
    """
    Use this tool to create a directory recursively.

    Args:
        dir_path: Path to the directory to create (relative to working directory or absolute)
    """
    context: AgentContext = runtime.context
    working_dir = str(context.working_dir)
    path = resolve_path(working_dir, dir_path)

    path.mkdir(parents=True, exist_ok=True)
    return f"Directory created: {path}"


create_dir.metadata = {
    "approval_config": {
        "name_only": True,
    }
}


@tool
async def move_file(
    source_path: str,
    destination_path: str,
    runtime: ToolRuntime[AgentContext],
) -> str:
    """
    Use this tool to move a file from source to destination.

    Args:
        source_path: Path to the source file (relative to working directory or absolute)
        destination_path: Path to the destination (relative to working directory or absolute)
    """
    context: AgentContext = runtime.context
    working_dir = str(context.working_dir)
    src = resolve_path(working_dir, source_path)
    dst = resolve_path(working_dir, destination_path)

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return f"File moved: {src} -> {dst}"


move_file.metadata = {
    "approval_config": {
        "name_only": True,
    }
}


@json_safe_tool
async def move_multiple_files(
    moves: Annotated[
        list[MoveOperation], Field(description="List of move operations to apply")
    ],
    runtime: ToolRuntime[AgentContext],
) -> str:
    """Use this tool to move multiple files in one operation."""
    context: AgentContext = runtime.context
    working_dir = str(context.working_dir)
    results = []
    for move in moves:
        src = resolve_path(working_dir, move.source)
        dst = resolve_path(working_dir, move.destination)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        results.append(f"{src} -> {dst}")
    return f"Files moved: {', '.join(results)}"


move_multiple_files.metadata = {
    "approval_config": {
        "name_only": True,
    }
}


@tool
async def delete_file(
    file_path: str,
    runtime: ToolRuntime[AgentContext],
) -> str:
    """
    Use this tool to delete a file.

    Args:
        file_path: Path to the file to delete (relative to working directory or absolute)
    """
    context: AgentContext = runtime.context
    working_dir = str(context.working_dir)
    path = resolve_path(working_dir, file_path)

    path.unlink()
    return f"File deleted: {path}"


delete_file.metadata = {
    "approval_config": {
        "name_only": True,
    }
}


@tool
async def insert_at_line(
    file_path: str,
    line_number: int,
    content: str,
    runtime: ToolRuntime[AgentContext],
) -> ToolMessage:
    """
    Use this tool to insert content at a specific line number.

    Args:
        file_path: Path to the file (relative to working directory or absolute)
        line_number: Line number to insert at (1-based, content inserted before this line)
        content: Content to insert
    """
    context: AgentContext = runtime.context
    working_dir = str(context.working_dir)
    path = resolve_path(working_dir, file_path)

    if not path.exists():
        raise ToolException(f"File does not exist: {path}")

    if line_number < 1:
        raise ToolException(f"Line number must be >= 1: {line_number}")

    with open(path, encoding="utf-8") as f:
        old_content = f.read()
        lines = old_content.splitlines(keepends=True)

    total_lines = len(lines)

    if line_number > total_lines + 1:
        raise ToolException(
            f"Line number {line_number} exceeds file length ({total_lines} lines)"
        )

    insert_index = line_number - 1

    if not content.endswith("\n") and insert_index < total_lines:
        content = content + "\n"

    new_lines = content.splitlines(keepends=True)
    lines[insert_index:insert_index] = new_lines

    new_content = "".join(lines)
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)

    diff_lines = generate_diff(
        old_content, new_content, context_lines=3, full_content=old_content
    )
    short_content = format_diff_rich(diff_lines)

    inserted_line_count = len(new_lines)
    return ToolMessage(
        name=insert_at_line.name,
        content=f"Inserted {inserted_line_count} line(s) at line {line_number} in {path}",
        tool_call_id=runtime.tool_call_id,
        short_content=short_content,
    )


insert_at_line.metadata = {
    "approval_config": {
        "name_only": True,
        "render_args_fn": _render_diff_args,
    }
}


@tool
async def delete_dir(
    dir_path: str,
    runtime: ToolRuntime[AgentContext],
) -> str:
    """
    Use this tool to delete a directory recursively.

    Args:
        dir_path: Path to the directory to delete (relative to working directory or absolute)
    """
    context: AgentContext = runtime.context
    working_dir = str(context.working_dir)
    path = resolve_path(working_dir, dir_path)

    shutil.rmtree(path)
    return f"Directory deleted: {path}"


delete_dir.metadata = {"approval_config": {}}


FILE_SYSTEM_TOOLS = [
    read_file,
    write_file,
    edit_file,
    create_dir,
    move_file,
    move_multiple_files,
    delete_file,
    insert_at_line,
    delete_dir,
]
