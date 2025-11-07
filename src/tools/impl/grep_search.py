import re
import shlex
from enum import Enum
from pathlib import Path

from langchain.tools import ToolRuntime, tool
from langchain_core.messages import ToolMessage
from langchain_core.tools import ToolException
from pydantic import BaseModel, Field

from src.agents.context import AgentContext
from src.core.logging import get_logger
from src.core.settings import settings
from src.utils.bash import execute_bash_command
from src.utils.file import get_file_language
from src.utils.path import resolve_path

logger = get_logger(__name__)


class OutputMode(str, Enum):
    """Output mode for grep search results."""

    CONTENT = "content"
    FILES = "files"
    BOTH = "both"


class GrepResult(BaseModel):
    """Represents a single grep search result."""

    file_path: str = Field(..., description="Path to the file")
    language: str | None = Field(None, description="Programming language")
    start_line: int | None = Field(None, description="Start line of the context")
    end_line: int | None = Field(None, description="End line of the context")
    content: str = Field(..., description="Matched content")


@tool
async def grep_search(
    search_query: str,
    directory_path: str,
    runtime: ToolRuntime[AgentContext],
    output_mode: OutputMode = OutputMode.BOTH,
) -> ToolMessage | str:
    """Search for code in the codebase and file/folder names using ripgrep-compatible Rust regex patterns.

    Args:
        search_query: Rust regex pattern (e.g., "(term1|term2|term3)")
        directory_path: Path to search directory (relative to working directory or absolute)
        output_mode: "files" (filenames only), "content" (code snippets), or "both" (default)

    Pattern Guidelines:
    - Analyze project structure to understand codebase organization and patterns
    - Consider technical domain, design patterns, and implementation approaches
    - Include semantic/conceptual terms, not just literal matches
    - Use context (e.g., 'function_name(' vs just 'function_name')
    - Combine terms with OR operator: (term1|term2|term3)
    """
    context: AgentContext = runtime.context
    working_dir = str(context.working_dir)

    resolved_path = resolve_path(working_dir, directory_path)
    absolute_directory_path = str(resolved_path)

    content_cmd = [
        "rg",
        "--line-number",
        "--no-binary",
        "--hidden",
        "--heading",
        "--ignore-case",
        "--glob",
        "!.git",
        f"--max-columns={settings.tool_settings.max_columns}",
        f"--context={settings.tool_settings.context_lines}",
        search_query,
        absolute_directory_path,
    ]
    filename_cmd = [
        "sh",
        "-c",
        f"rg --files --hidden --glob '!.git' {shlex.quote(absolute_directory_path)} | rg -i {shlex.quote(search_query)}",
    ]

    content_status, content_stdout, content_stderr = await execute_bash_command(
        content_cmd, cwd=working_dir
    )
    if content_status not in (0, 1):
        raise ToolException(content_stderr)
    content_results = _parse_results(
        content_stdout, settings.tool_settings.search_limit
    )

    filename_results: list[GrepResult] = []
    if output_mode in (OutputMode.FILES, OutputMode.BOTH):
        filename_status, filename_stdout, filename_stderr = await execute_bash_command(
            filename_cmd
        )
        if filename_status not in (0, 1):
            raise ToolException(filename_stderr)
        filename_results = _parse_filename_results(filename_stdout)

    all_results = (
        _combine_results(content_results, filename_results, files_only=True)
        if output_mode == OutputMode.FILES
        else (
            content_results
            if output_mode == OutputMode.CONTENT
            else _combine_results(content_results, filename_results)
        )
    )

    dir_name = Path(absolute_directory_path).name
    short_content = {
        OutputMode.FILES: f"Found {len(all_results)} filename matches for '{search_query}' in {dir_name}",
        OutputMode.CONTENT: f"Found {len(all_results)} content matches for '{search_query}' in {dir_name}",
        OutputMode.BOTH: f"Found {len(all_results)} matches for '{search_query}' in {dir_name} ({len(content_results)} content, {len(filename_results)} filenames)",
    }[output_mode]

    return ToolMessage(
        name=grep_search.name,
        content=_format_results(all_results),
        tool_call_id=runtime.tool_call_id,
        short_content=short_content,
    )


grep_search.metadata = {
    "approval_config": {
        "name_only": True,
    }
}


def _format_results(results: list[GrepResult]) -> str:
    """Format results for display."""
    if not results:
        return "No results found."

    formatted = []
    for r in results:
        file_info = (
            r.file_path
            if r.start_line is None
            else f"{r.file_path}:{r.start_line}-{r.end_line}"
        )
        if r.content.strip():
            formatted.append(f"{file_info}\n{r.content.strip()}")
        else:
            formatted.append(file_info)

    separator = "\n\n" if any(r.content.strip() for r in results) else "\n"
    return separator.join(formatted)


def _split_chunks(lines: list[str], limit: int) -> list[list[str]]:
    """Split lines into chunks separated by '--'."""
    chunks: list[list[str]] = []
    current_chunk: list[str] = []
    chunk_count = 0

    for line in lines:
        if chunk_count >= limit * 2:
            break
        if line.strip() == "--":
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = []
        else:
            current_chunk.append(line)
        chunk_count += 1

    if current_chunk:
        chunks.append(current_chunk)
    return chunks


def _parse_results(output: str, limit: int) -> list[GrepResult]:
    """Parse grep output into GrepResult objects."""
    results = []

    for section in filter(None, re.split(r"\n\n+", output.strip())):
        lines = section.strip().split("\n")
        if not lines:
            continue

        file_path = lines[0].strip()
        for chunk in _split_chunks(lines[1:], limit):
            line_numbers, chunk_lines = [], []

            for line in chunk:
                if match := re.match(r"^(\d+)[:-](.*)$", line.strip()):
                    line_numbers.append(int(match.group(1)))
                    chunk_lines.append(match.group(2))

            if line_numbers:
                results.append(
                    GrepResult(
                        file_path=file_path,
                        language=get_file_language(file_path),
                        start_line=min(line_numbers),
                        end_line=max(line_numbers),
                        content="\n".join(chunk_lines),
                    )
                )

    logger.info(f"Found {len(results)} content search results")
    return results


def _parse_filename_results(output: str) -> list[GrepResult]:
    """Parse filename search output into GrepResult objects."""
    if not output.strip():
        return []

    results = [
        GrepResult(
            file_path=fp,
            language=get_file_language(fp),
            start_line=None,
            end_line=None,
            content="",
        )
        for line in output.strip().split("\n")
        if (fp := line.strip())
    ]

    logger.info(f"Found {len(results)} filename search results")
    return results


def _combine_results(
    content_results: list[GrepResult],
    filename_results: list[GrepResult],
    files_only: bool = False,
) -> list[GrepResult]:
    """Combine and deduplicate content and filename search results."""
    seen_files = set()
    combined_results = []

    if files_only:
        for result in filename_results:
            if result.file_path not in seen_files:
                combined_results.append(result)
                seen_files.add(result.file_path)

        for result in content_results:
            if result.file_path not in seen_files:
                combined_results.append(
                    GrepResult(
                        file_path=result.file_path,
                        language=result.language,
                        start_line=None,
                        end_line=None,
                        content="",
                    )
                )
                seen_files.add(result.file_path)
    else:
        for result in content_results:
            combined_results.append(result)
            seen_files.add(result.file_path)

        for result in filename_results:
            if result.file_path not in seen_files:
                combined_results.append(result)
                seen_files.add(result.file_path)

    return combined_results


GREP_SEARCH_TOOLS = [grep_search]
