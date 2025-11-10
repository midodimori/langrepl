"""Tests for image utility functions."""

import base64
import binascii

import pytest

from src.utils.image import (
    get_image_mime_type,
    is_image_file,
    is_image_path,
    is_supported_image,
    read_image_as_base64,
)


class TestIsImageFile:
    """Tests for is_image_file function."""

    def test_common_formats(self, create_test_image):
        """Test that common image formats are recognized."""
        for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]:
            path = create_test_image("test", ext)
            assert is_image_file(path)

    def test_non_image_rejected(self, tmp_path):
        """Test that non-image files are rejected."""
        for ext in [".txt", ".pdf", ".py"]:
            path = tmp_path / f"test{ext}"
            path.write_text("test")
            assert not is_image_file(path)


class TestIsSupportedImage:
    """Tests for is_supported_image function."""

    def test_supported_extensions(self, create_test_image):
        """Test that supported image extensions are recognized."""
        for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]:
            path = create_test_image("test", ext)
            assert is_supported_image(path)

    def test_unsupported_extensions(self, tmp_path):
        """Test that unsupported extensions are rejected."""
        unsupported = [".txt", ".pdf", ".svg", ".bmp", ".tiff"]
        for ext in unsupported:
            path = tmp_path / f"test{ext}"
            path.write_text("test")
            assert not is_supported_image(path)

    def test_case_insensitive(self, create_test_image):
        """Test that extension matching is case-insensitive."""
        path = create_test_image("test", ".PNG")
        assert is_supported_image(path)

        path = create_test_image("test2", ".JPG")
        assert is_supported_image(path)


class TestGetImageMimeType:
    """Tests for get_image_mime_type function."""

    def test_common_image_types(self, create_test_image):
        """Test MIME type detection for common image formats."""
        test_cases = [
            (".png", "image/png"),
            (".jpg", "image/jpeg"),
            (".jpeg", "image/jpeg"),
            (".gif", "image/gif"),
            (".webp", "image/webp"),
        ]

        for ext, expected_mime in test_cases:
            path = create_test_image("test", ext)
            assert get_image_mime_type(path) == expected_mime

    def test_unsupported_format(self, tmp_path):
        """Test that unsupported formats return None."""
        path = tmp_path / "test.txt"
        path.write_text("not an image")
        assert get_image_mime_type(path) is None


class TestReadImageAsBase64:
    """Tests for read_image_as_base64 function."""

    def test_reads_and_encodes_image(self, create_test_image):
        """Test that image is read and properly base64 encoded."""
        path = create_test_image("test", ".png")
        result = read_image_as_base64(path)

        # Should be a non-empty base64 string
        assert isinstance(result, str)
        assert len(result) > 0

        # Should be valid base64
        try:
            decoded = base64.b64decode(result)
            assert len(decoded) > 0
        except (binascii.Error, ValueError) as e:
            pytest.fail(f"Invalid base64 encoding: {e}")

    def test_file_not_found(self, tmp_path):
        """Test that FileNotFoundError is raised for missing files."""
        nonexistent = tmp_path / "nonexistent.png"
        with pytest.raises(FileNotFoundError):
            read_image_as_base64(nonexistent)

    def test_not_a_file(self, tmp_path):
        """Test that ValueError is raised when path is a directory."""
        directory = tmp_path / "test_dir"
        directory.mkdir()
        with pytest.raises(ValueError, match="not a file"):
            read_image_as_base64(directory)

    def test_different_formats(self, create_test_image):
        """Test reading different image formats."""
        for ext in [".png", ".jpg", ".gif", ".webp"]:
            path = create_test_image("test", ext)
            result = read_image_as_base64(path)
            assert isinstance(result, str)
            assert len(result) > 0


class TestIsImagePath:
    """Tests for is_image_path function."""

    def test_valid_absolute_image_path(self, create_test_image):
        """Test that valid absolute paths to images are recognized."""
        path = create_test_image("test", ".png")
        assert is_image_path(str(path))

    def test_relative_path_rejected(self, create_test_image):
        """Test that relative paths are rejected."""
        # Create image in current directory
        path = create_test_image("test", ".png")
        relative_path = path.name  # Just the filename
        assert not is_image_path(relative_path)

    def test_nonexistent_path_rejected(self):
        """Test that nonexistent paths are rejected."""
        assert not is_image_path("/nonexistent/path/to/image.png")

    def test_svg_format_accepted(self, tmp_path):
        """Test that SVG images are accepted (validation at submit)."""
        path = tmp_path / "test.svg"
        path.write_text("<svg></svg>")
        assert is_image_path(str(path))

    def test_directory_rejected(self, tmp_path):
        """Test that directories are rejected."""
        directory = tmp_path / "test.png"  # Name looks like image but is directory
        directory.mkdir()
        assert not is_image_path(str(directory))

    def test_whitespace_handling(self, create_test_image):
        """Test that paths with surrounding whitespace are handled."""
        path = create_test_image("test", ".png")
        assert is_image_path(f"  {path}  ")

    def test_non_path_strings(self):
        """Test that random strings are rejected."""
        assert not is_image_path("just some text")
        assert not is_image_path("@:image:relative/path.png")
