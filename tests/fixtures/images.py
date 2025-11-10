"""Image-related test fixtures."""

import base64
from pathlib import Path

import pytest


@pytest.fixture
def create_test_image(temp_dir):
    """Create a minimal test image.

    Args:
        temp_dir: Temporary directory fixture

    Returns:
        Callable that creates test images with various formats
    """

    def _create_image(filename: str, extension: str = ".png") -> Path:
        """Create a test image file.

        Args:
            filename: Name for the image file (without extension)
            extension: File extension (default: .png)

        Returns:
            Path to the created image file
        """
        # Minimal 1x1 PNG image (67 bytes)
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )

        # Minimal 1x1 JPEG image
        jpeg_data = base64.b64decode(
            "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAAAAAAAAAAAAAAAAAACv/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q=="
        )

        # Minimal 1x1 GIF image
        gif_data = base64.b64decode(
            "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
        )

        # Minimal 1x1 WebP image
        webp_data = base64.b64decode(
            "UklGRiQAAABXRUJQVlA4IBgAAAAwAQCdASoBAAEAAwA0JaQAA3AA/vuUAAA="
        )

        image_data_map = {
            ".png": png_data,
            ".jpg": jpeg_data,
            ".jpeg": jpeg_data,
            ".gif": gif_data,
            ".webp": webp_data,
        }

        file_path = temp_dir / f"{filename}{extension}"
        file_path.write_bytes(image_data_map.get(extension, png_data))
        return file_path

    return _create_image
