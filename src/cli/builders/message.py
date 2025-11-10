"""Message content builder."""

import re
from pathlib import Path
from typing import Any

from src.cli.resolvers import FileResolver, ImageResolver, RefType


class MessageContentBuilder:
    """Builds message content with multimodal support."""

    def __init__(self, working_dir: Path):
        """Initialize message content builder."""
        self.working_dir = working_dir
        self.resolvers = {
            RefType.FILE: FileResolver(),
            RefType.IMAGE: ImageResolver(),
        }

    def extract_references(self, text: str) -> dict[RefType, list[str]]:
        """Extract all typed references and standalone paths from text."""
        references: dict[RefType, list[str]] = {}

        ref_pattern = r"@:([\w]+):((?:[^\s?,!.;]|[.,!?;](?!\s|$))+)"
        for match in re.finditer(ref_pattern, text):
            type_str, value = match.groups()
            try:
                ref_type = RefType(type_str)
                if ref_type not in references:
                    references[ref_type] = []
                references[ref_type].append(value)
            except ValueError:
                continue

        for word in text.split():
            if word.startswith("@:"):
                continue
            # Strip common punctuation from end of word
            cleaned_word = word.rstrip(".,!?;:")
            for resolver in self.resolvers.values():
                if resolver.is_standalone_reference(cleaned_word):
                    ref_type = resolver.type
                    if ref_type not in references:
                        references[ref_type] = []
                    references[ref_type].append(cleaned_word)
                    break

        return references

    def build(
        self, text: str
    ) -> tuple[str | list[str | dict[str, Any]], dict[str, str]]:
        """Build message content with multimodal support.

        Raises:
            FileNotFoundError: If referenced file/image doesn't exist
            ValueError: If referenced file/image is invalid
        """
        references = self.extract_references(text)

        if not references:
            return text, {}

        ctx = {"working_dir": str(self.working_dir)}
        reference_mapping = {}
        text_content = text
        errors: list[str] = []

        for ref_type, paths in references.items():
            resolver = self.resolvers[ref_type]
            for path in paths:
                resolved = resolver.resolve(path, ctx)
                reference_mapping[path] = resolved

                ref_pattern = rf"@:{ref_type.value}:{re.escape(path)}"
                try:
                    if resolver.build_content_block(resolved):
                        text_content = re.sub(ref_pattern, "", text_content)
                    else:
                        text_content = re.sub(ref_pattern, resolved, text_content)
                except (FileNotFoundError, ValueError) as e:
                    errors.append(str(e))
                    text_content = re.sub(ref_pattern, "", text_content)

        if errors:
            raise ValueError("\n".join(errors))

        content_blocks: list[str | dict[str, Any]] = []

        if text_content.strip():
            content_blocks.append({"type": "text", "text": text_content.strip()})

        for ref_type, paths in references.items():
            resolver = self.resolvers[ref_type]
            for path in paths:
                resolved = reference_mapping[path]
                try:
                    if block := resolver.build_content_block(resolved):
                        content_blocks.append(block)
                except (FileNotFoundError, ValueError):
                    pass

        if len(content_blocks) == 1:
            first_block = content_blocks[0]
            if isinstance(first_block, dict) and first_block.get("type") == "text":
                return first_block["text"], reference_mapping

        return content_blocks, reference_mapping
