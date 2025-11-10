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
    is_image_file,
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

        # Build extension filters for git (glob patterns) and fd (-e flags)
        git_globs = " ".join(
            quote(f"*.{ext.lstrip('.')}") for ext in SUPPORTED_IMAGE_EXTENSIONS
        )
        fd_flags = " ".join(
            f"-e {ext.lstrip('.')}" for ext in SUPPORTED_IMAGE_EXTENSIONS
        )

        safe_pattern = quote(pattern) if pattern else ""
        commands = [
            # Git-based search
            (
                f"(git ls-files {git_globs} && git ls-files -o --exclude-standard {git_globs}) | grep -i {safe_pattern} | {head}"
                if pattern
                else f"(git ls-files {git_globs} && git ls-files -o --exclude-standard {git_globs}) | {head}"
            ),
            # fd-based search
            (
                f"fd --type f {fd_flags} -i {safe_pattern} | {head}"
                if pattern
                else f"fd --type f {fd_flags} | {head}"
            ),
        ]

        for base_cmd in commands:
            cmd = ["sh", "-c", base_cmd]
            return_code, stdout, _ = await execute_bash_command(
                cmd, cwd=str(working_dir), timeout=1
            )
            if return_code == 0 and stdout:
                # Filter results to only include image files
                results = [f for f in stdout.strip().split("\n") if f]
                # Verify each result is actually an image
                filtered_results = []
                for file_path in results:
                    full_path = working_dir / file_path
                    if full_path.exists() and is_image_file(full_path):
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
            if resolved.exists():
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
        """Build image content block for multimodal message.

        Raises:
            FileNotFoundError: If image doesn't exist
            ValueError: If unsupported format or read error
        """
        path_obj = Path(path)

        if not path_obj.exists():
            raise FileNotFoundError(f"Image not found: {path}")

        if not is_supported_image(path_obj):
            raise ValueError(f"Unsupported format: {path_obj.suffix}")

        base64_data = read_image_as_base64(path_obj)
        mime_type = get_image_mime_type(path_obj)

        if not mime_type:
            raise ValueError(f"Cannot determine MIME type: {path}")

        return {
            "type": "image",
            "source_type": "base64",
            "data": base64_data,
            "mime_type": mime_type,
        }
