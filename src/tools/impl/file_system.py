import shutil

from langchain.tools import ToolRuntime, tool
from langchain_core.messages import ToolMessage
from langchain_core.tools import ToolException
from pydantic import BaseModel, Field

from src.agents.context import AgentContext
from src.cli.theme import theme
from src.utils.path import resolve_path
from src.utils.render import format_diff_rich, generate_diff


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
    """
    Get a string value for `attr` from either a dict or a Pydantic model.
    
    Parameters:
        obj (dict | BaseModel): Source object to read the attribute from.
        attr (str): Attribute name or dict key to retrieve.
        default (str): Value returned when the attribute/key is missing (defaults to "").
    
    Returns:
        str: The attribute or key value if present, otherwise `default`.
    """
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)


def _render_diff_args(args: dict, config: dict) -> str:
    """
    Produce a colored diff preview for the provided file arguments.
    
    Generates a diff preview for either a list of edit operations (from `edits`) or a single new `content` value. When a working directory is available in `config["configurable"]["working_dir"]` and the referenced file exists, the file's full current contents are used to provide richer diffs. The returned string begins with a colored "Path" header and contains the rendered diff suitable for display to a user.
    
    Parameters:
        args (dict): Input arguments containing at least `file_path` (str). Optionally includes:
            - `edits` (list): Sequence of edit objects or dicts with `old_content` and `new_content`.
            - `content` (str): New file content used when `edits` is not provided.
        config (dict): Configuration dictionary that may include a `configurable` mapping with `working_dir` (str) used to resolve the file path and load full file contents for context.
    
    Returns:
        str: Colored preview string that starts with a path header and contains the rendered diff.
    """
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
    if edits:
        all_diff_sections = []
        for edit in edits:
            old_content = _get_attr(edit, "old_content")
            new_content = _get_attr(edit, "new_content")
            diff_lines = generate_diff(
                old_content, new_content, context_lines=3, full_content=full_content
            )
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
    file_path: str,
    start_line: int,
    runtime: ToolRuntime[AgentContext],
    limit: int = 500,
) -> ToolMessage:
    """
    Read a file and return a paginated, numbered view of its lines.
    
    Parameters:
        file_path (str): Path to the file, relative to the agent working directory or absolute.
        start_line (int): 0-based index of the first line to read.
        limit (int): Maximum number of lines to include (default: 500).
    
    Returns:
        ToolMessage: Message whose `content` contains the selected lines with line numbers and a bracketed summary
        (`[start-end, lines_read/total_lines]`), and whose `short_content` summarizes the read range (e.g., "Read 0-9 of 100 lines from file.txt").
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
    Create a new file at the given path with the provided content if the file does not already exist.
    
    Parameters:
        file_path (str): Path to the file to create; interpreted relative to the agent working directory when not absolute.
        content (str): File contents to write.
        runtime (ToolRuntime[AgentContext]): Execution runtime providing the agent context (working directory and tool_call_id).
    
    Returns:
        ToolMessage: Confirmation message naming the written file and containing a rendered diff preview of the new file.
    
    Raises:
        ToolException: If a file already exists at the resolved path.
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


@tool
async def edit_file(
    file_path: str,
    edits: list[EditOperation],
    runtime: ToolRuntime[AgentContext],
) -> ToolMessage:
    """
    Edit a file by applying a sequence of replacement edits in order.
    
    Parameters:
        file_path (str): Path to the file to edit (relative to the agent working directory or absolute).
        edits (list[EditOperation]): List of replacement operations applied sequentially; each operation must match existing text in the file.
    
    Returns:
        ToolMessage: Confirmation message that includes the edited file path and a short diff preview of the applied edits.
    
    Raises:
        ToolException: If the target file does not exist or if any edit's `old_content` is not found in the file.
    """
    context: AgentContext = runtime.context
    working_dir = str(context.working_dir)
    path = resolve_path(working_dir, file_path)

    if not path.exists():
        raise ToolException(f"File does not exist: {path}")

    with open(path, encoding="utf-8") as f:
        current_content = f.read()

    for edit in edits:
        if edit.old_content not in current_content:
            raise ToolException(f"Old content not found in file: {path}")

    updated_content = current_content
    for edit in edits:
        updated_content = updated_content.replace(edit.old_content, edit.new_content)

    with open(path, "w", encoding="utf-8") as f:
        f.write(updated_content)

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
    Create a directory and any missing parent directories at the given path.
    
    Parameters:
        dir_path (str): Path to create. If relative, it is resolved against the agent's working directory.
    
    Returns:
        message (str): Confirmation message containing the created directory path, e.g. "Directory created: /abs/path".
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
    Move a file from a source path to a destination path, resolving both against the agent's working directory when relative.
    
    Parameters:
        source_path (str): Source file path, either absolute or relative to the agent's working directory.
        destination_path (str): Destination file path, either absolute or relative to the agent's working directory.
    
    Returns:
        message (str): Confirmation message describing the moved source and destination paths.
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


@tool
async def move_multiple_files(
    moves: list[MoveOperation],
    runtime: ToolRuntime[AgentContext],
) -> str:
    """
    Move multiple files according to the provided move operations.
    
    Each MoveOperation's source and destination are resolved against the agent's working directory; destination parent directories are created as needed.
    
    Parameters:
        moves (list[MoveOperation]): Operations specifying source and destination paths (relative or absolute).
    
    Returns:
        str: A summary message listing all moved files in the form "src -> dst".
    """
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
    Delete the file at the given path.
    
    Parameters:
        file_path (str): Path to the file to delete; resolved against the agent working directory (runtime.context.working_dir) when relative.
        runtime (ToolRuntime[AgentContext]): Execution runtime providing the agent context used for path resolution.
    
    Returns:
        str: Confirmation message containing the deleted file path.
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
    Insert text into a file at the specified 1-based line number.
    
    If `line_number` is between 1 and the file's length, the content is inserted before that line. If `line_number` equals the file's length + 1, the content is appended. If `content` does not end with a newline and the insertion point is not at the end of the file, a newline is appended to `content` before insertion.
    
    Parameters:
        file_path (str): Path to the file, relative to the agent's working directory or absolute.
        line_number (int): 1-based line number at which to insert; insertion occurs before this line.
        content (str): Text to insert into the file.
        runtime (ToolRuntime[AgentContext]): Runtime providing the agent context and tool_call_id.
    
    Returns:
        ToolMessage: Confirmation message describing how many lines were inserted and the target path. `short_content` contains a rendered diff between the original and updated file content.
    
    Raises:
        ToolException: If the file does not exist, `line_number` is less than 1, or `line_number` exceeds the file length + 1.
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
    Delete a directory and all of its contents.
    
    Deletes the directory specified by `dir_path`. `dir_path` may be absolute or relative to the agent's working directory; the function resolves it before removal.
    
    Parameters:
        dir_path (str): Path to the directory to delete (absolute or relative to the agent working directory).
    
    Returns:
        str: Confirmation message containing the resolved path of the deleted directory.
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