"""Image reference resolver."""

from pathlib import Path
from shlex import quote
from typing import Any

from prompt_toolkit.completion import Completion

from src.cli.resolvers.base import RefType, Resolver
from src.utils.bash import execute_bash_command
from src.utils.image import (
    SUPPORTED_IMAGE_EXTENSIONS,
    get_image_mime_type,
    is_image_path,
    is_supported_image,
    read_image_as_base64,
)
from src.utils.path import resolve_path


class ImageResolver(Resolver):
    """Resolves image references."""

    type = RefType.IMAGE

    @staticmethod
    async def _get_image_files(
        working_dir: Path, limit: int | None = None, pattern: str = ""
    ) -> list[str]:
        """Get list of image files using git or fd.

        Args:
            working_dir: Working directory to search in
            limit: Maximum number of results to return
            pattern: Optional pattern to filter results

        Returns:
            List of image file paths
        """
        head = f"head -n {limit}" if limit else "cat"

        # Build extension filter for common image formats
        extensions = " ".join(f"-e {ext}" for ext in SUPPORTED_IMAGE_EXTENSIONS)

        safe_pattern = quote(pattern) if pattern else ""
        commands = [
            # Git-based search
            (
                f"git ls-files {extensions} | grep -i {safe_pattern} | {head}"
                if pattern
                else f"git ls-files {extensions} | {head}"
            ),
            # fd-based search
            (
                f"fd --type f {extensions} -i {safe_pattern} | {head}"
                if pattern
                else f"fd --type f {extensions} | {head}"
            ),
        ]

        for base_cmd in commands:
            cmd = ["sh", "-c", base_cmd]
            return_code, stdout, _ = await execute_bash_command(
                cmd, cwd=str(working_dir), timeout=1
            )
            if return_code == 0 and stdout:
                # Filter results to only include supported image files
                results = [f for f in stdout.strip().split("\n") if f]
                # Verify each result is actually a supported image
                filtered_results = []
                for file_path in results:
                    full_path = working_dir / file_path
                    if full_path.exists() and is_supported_image(full_path):
                        filtered_results.append(file_path)
                if filtered_results:
                    return filtered_results

        return []

    def resolve(self, ref: str, ctx: dict) -> str:
        """Resolve image reference to an absolute path.

        Args:
            ref: Image reference string (relative or absolute path)
            ctx: Context dictionary with working_dir

        Returns:
            Absolute path to the image file
        """
        working_dir = ctx.get("working_dir", "")
        try:
            resolved = resolve_path(str(working_dir), ref)
            # Validate that the resolved path is a supported image
            if resolved.exists() and is_supported_image(resolved):
                return str(resolved)
            return ref
        except Exception:
            return ref

    async def complete(self, fragment: str, ctx: dict, limit: int) -> list[Completion]:
        """Get image file completions.

        Args:
            fragment: Partial filename to complete
            ctx: Context dictionary with working_dir and start_position
            limit: Maximum number of completions to return

        Returns:
            List of Completion objects for matching image files
        """
        completions: list[Completion] = []
        working_dir = Path(ctx.get("working_dir", ""))

        try:
            images = await self._get_image_files(
                working_dir, limit=limit, pattern=fragment
            )

            start_position = ctx.get("start_position", 0)

            for image_path in images:
                display_text = f"@:image:{image_path}"
                completion_text = f"@:image:{image_path}"

                completions.append(
                    Completion(
                        completion_text,
                        start_position=start_position,
                        display=display_text,
                        style="class:file-completion",
                    )
                )

        except Exception:
            pass

        return completions

    def is_standalone_reference(self, text: str) -> bool:
        """Check if text is a standalone image path."""
        return is_image_path(text)

    def build_content_block(self, path: str) -> dict[str, Any] | None:
        """Build image content block for multimodal message."""
        try:
            path_obj = Path(path)
            base64_data = read_image_as_base64(path_obj)
            mime_type = get_image_mime_type(path_obj)

            if mime_type:
                return {
                    "type": "image",
                    "source_type": "base64",
                    "data": base64_data,
                    "mime_type": mime_type,
                }
        except Exception:
            pass

        return None
