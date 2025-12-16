"""Image handling utilities for multimodal support."""

import base64
import mimetypes
from pathlib import Path

# Supported image formats for common multimodal models
SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
SUPPORTED_IMAGE_MIMES = {"image/png", "image/jpeg", "image/gif", "image/webp"}


def is_image_file(path: Path) -> bool:
    """Check if file is an image (any format)."""
    mime_type, _ = mimetypes.guess_type(str(path))
    return mime_type is not None and mime_type.startswith("image/")


def is_supported_image(path: Path) -> bool:
    """Check if file is a supported image format.

    Args:
        path: Path to the image file

    Returns:
        True if the file has a supported image extension
    """
    return path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS


def get_image_mime_type(path: Path) -> str | None:
    """Get MIME type for an image file.

    Args:
        path: Path to the image file

    Returns:
        MIME type string (e.g., 'image/jpeg') or None if cannot be determined
    """
    mime_type, _ = mimetypes.guess_type(str(path))

    if mime_type and mime_type in SUPPORTED_IMAGE_MIMES:
        return mime_type

    # Fallback mapping for common extensions
    extension_to_mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }

    return extension_to_mime.get(path.suffix.lower())


def read_image_as_base64(path: Path) -> str:
    """Read image file and encode as base64 string.

    Args:
        path: Path to the image file

    Returns:
        Base64-encoded string of the image data

    Raises:
        FileNotFoundError: If the image file doesn't exist
        OSError: If there's an error reading the file
    """
    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {path}")

    if not path.is_file():
        raise ValueError(f"Path is not a file: {path}")

    with open(path, "rb") as f:
        image_data = f.read()

    return base64.b64encode(image_data).decode("utf-8")


def is_image_path(text: str) -> bool:
    """Check if a string looks like an absolute path to an image file.

    Args:
        text: String to check

    Returns:
        True if the string is an absolute path to an existing image file
    """
    try:
        path = Path(text.strip())
        return (
            path.is_absolute()
            and path.exists()
            and path.is_file()
            and is_image_file(path)
        )
    except (OSError, ValueError):
        return False
