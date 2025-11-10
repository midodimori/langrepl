"""Tests for ImageResolver."""

import base64
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.cli.resolvers.image import ImageResolver


@pytest.fixture
def create_test_images(tmp_path):
    """Create test image files in a temporary directory."""

    def _create_images() -> dict[str, Path]:
        """Create various test image files.

        Returns:
            Dictionary mapping image names to their paths
        """
        # Minimal 1x1 PNG image
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )

        # Create subdirectory structure
        img_dir = tmp_path / "images"
        img_dir.mkdir()

        images = {
            "photo1.png": tmp_path / "photo1.png",
            "photo2.jpg": tmp_path / "photo2.jpg",
            "icon.gif": img_dir / "icon.gif",
            "banner.webp": img_dir / "banner.webp",
        }

        for path in images.values():
            path.write_bytes(png_data)

        return images

    return _create_images


class TestImageResolverResolve:
    """Tests for ImageResolver.resolve method."""

    def test_resolve_relative_path(self, tmp_path, create_test_images):
        """Test resolving a relative image path."""
        images = create_test_images()
        resolver = ImageResolver()
        ctx = {"working_dir": str(tmp_path)}

        result = resolver.resolve("photo1.png", ctx)
        assert result == str(images["photo1.png"])

    def test_resolve_absolute_path(self, tmp_path, create_test_images):
        """Test resolving an absolute image path."""
        images = create_test_images()
        resolver = ImageResolver()
        ctx = {"working_dir": str(tmp_path)}

        abs_path = str(images["photo1.png"])
        result = resolver.resolve(abs_path, ctx)
        assert result == abs_path

    def test_resolve_subdirectory_path(self, tmp_path, create_test_images):
        """Test resolving an image in a subdirectory."""
        images = create_test_images()
        resolver = ImageResolver()
        ctx = {"working_dir": str(tmp_path)}

        result = resolver.resolve("images/icon.gif", ctx)
        assert result == str(images["icon.gif"])

    def test_resolve_nonexistent_image(self, tmp_path):
        """Test resolving a nonexistent image returns original ref."""
        resolver = ImageResolver()
        ctx = {"working_dir": str(tmp_path)}

        result = resolver.resolve("nonexistent.png", ctx)
        assert result == "nonexistent.png"

    def test_resolve_unsupported_format(self, tmp_path):
        """Test resolving unsupported image format resolves path."""
        # Create an SVG file (unsupported for LLMs but valid image)
        svg_file = tmp_path / "image.svg"
        svg_file.write_text("<svg></svg>")

        resolver = ImageResolver()
        ctx = {"working_dir": str(tmp_path)}

        result = resolver.resolve("image.svg", ctx)
        # Should resolve to absolute path (validation happens at submit)
        assert result == str(svg_file)


class TestImageResolverComplete:
    """Tests for ImageResolver.complete method."""

    @pytest.mark.asyncio
    async def test_complete_returns_image_files(self, tmp_path, create_test_images):
        """Test that completion returns only image files."""
        create_test_images()

        # Mock the _get_image_files method to return known images
        resolver = ImageResolver()
        with patch.object(
            resolver,
            "_get_image_files",
            new_callable=AsyncMock,
            return_value=["photo1.png", "photo2.jpg", "images/icon.gif"],
        ):
            ctx = {"working_dir": str(tmp_path), "start_position": -7}
            completions = await resolver.complete("", ctx, limit=10)

            assert len(completions) == 3
            assert completions[0].text == "@:image:photo1.png"
            assert completions[1].text == "@:image:photo2.jpg"
            assert completions[2].text == "@:image:images/icon.gif"

    @pytest.mark.asyncio
    async def test_complete_with_pattern(self, tmp_path, create_test_images):
        """Test completion with a search pattern."""
        create_test_images()

        resolver = ImageResolver()
        with patch.object(
            resolver,
            "_get_image_files",
            new_callable=AsyncMock,
            return_value=["photo1.png", "photo2.jpg"],
        ):
            ctx = {"working_dir": str(tmp_path), "start_position": -7}
            completions = await resolver.complete("photo", ctx, limit=10)

            assert len(completions) == 2
            assert all("photo" in c.text for c in completions)

    @pytest.mark.asyncio
    async def test_complete_respects_limit(self, tmp_path, create_test_images):
        """Test that completion respects the limit parameter."""
        create_test_images()

        resolver = ImageResolver()
        with patch.object(
            resolver,
            "_get_image_files",
            new_callable=AsyncMock,
            return_value=["photo1.png", "photo2.jpg"],
        ):
            ctx = {"working_dir": str(tmp_path), "start_position": -7}
            completions = await resolver.complete("", ctx, limit=2)

            assert len(completions) == 2

    @pytest.mark.asyncio
    async def test_complete_handles_exceptions(self, tmp_path):
        """Test that completion handles exceptions gracefully."""
        resolver = ImageResolver()

        # Mock _get_image_files to raise an exception
        with patch.object(
            resolver, "_get_image_files", new_callable=AsyncMock, side_effect=Exception
        ):
            ctx = {"working_dir": str(tmp_path), "start_position": -7}
            completions = await resolver.complete("", ctx, limit=10)

            # Should return empty list on exception
            assert completions == []

    @pytest.mark.asyncio
    async def test_complete_start_position(self, tmp_path, create_test_images):
        """Test that completions use correct start position."""
        create_test_images()

        resolver = ImageResolver()
        with patch.object(
            resolver,
            "_get_image_files",
            new_callable=AsyncMock,
            return_value=["photo1.png"],
        ):
            ctx = {"working_dir": str(tmp_path), "start_position": -15}
            completions = await resolver.complete("", ctx, limit=10)

            assert completions[0].start_position == -15


class TestImageResolverGetImageFiles:
    """Tests for ImageResolver._get_image_files method."""

    @pytest.mark.asyncio
    async def test_get_image_files_filters_by_extension(self, tmp_path):
        """Test that _get_image_files only returns image files."""
        # Create mix of files
        (tmp_path / "photo.png").write_bytes(b"PNG")
        (tmp_path / "doc.txt").write_text("text")
        (tmp_path / "script.py").write_text("code")

        # Mock execute_bash_command to return all files
        with patch(
            "src.cli.resolvers.image.execute_bash_command",
            new_callable=AsyncMock,
            return_value=(0, "photo.png\ndoc.txt\nscript.py\n", ""),
        ):
            resolver = ImageResolver()
            results = await resolver._get_image_files(tmp_path, limit=10, pattern="")

            # Should only return the image file
            assert "photo.png" in results
            assert "doc.txt" not in results
            assert "script.py" not in results

    @pytest.mark.asyncio
    async def test_get_image_files_handles_empty_results(self, tmp_path):
        """Test that _get_image_files handles no results."""
        with patch(
            "src.cli.resolvers.image.execute_bash_command",
            new_callable=AsyncMock,
            return_value=(0, "", ""),
        ):
            resolver = ImageResolver()
            results = await resolver._get_image_files(tmp_path, limit=10, pattern="")

            assert results == []

    @pytest.mark.asyncio
    async def test_get_image_files_handles_command_failure(self, tmp_path):
        """Test that _get_image_files handles command failures."""
        # Mock both git and fd commands to fail
        with patch(
            "src.cli.resolvers.image.execute_bash_command",
            new_callable=AsyncMock,
            return_value=(1, "", "error"),
        ):
            resolver = ImageResolver()
            results = await resolver._get_image_files(tmp_path, limit=10, pattern="")

            assert results == []
