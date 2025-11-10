"""Tests for MessageContentBuilder."""

from src.cli.builders.message import MessageContentBuilder
from src.cli.resolvers import RefType


class TestExtractReferences:
    """Tests for extract_references method."""

    def test_extract_single_reference(self, temp_dir):
        """Test extracting a single @:image: reference."""
        builder = MessageContentBuilder(temp_dir)
        content = "Look at this @:image:photo.png image"

        refs = builder.extract_references(content)

        assert RefType.IMAGE in refs
        assert refs[RefType.IMAGE] == ["photo.png"]

    def test_extract_multiple_references(self, temp_dir):
        """Test extracting multiple @:image: references."""
        builder = MessageContentBuilder(temp_dir)
        content = "Compare @:image:photo1.png and @:image:photo2.jpg"

        refs = builder.extract_references(content)

        assert RefType.IMAGE in refs
        assert refs[RefType.IMAGE] == ["photo1.png", "photo2.jpg"]

    def test_extract_with_absolute_path(self, temp_dir):
        """Test extracting reference with absolute path."""
        builder = MessageContentBuilder(temp_dir)
        content = "Check @:image:/Users/test/photo.png"

        refs = builder.extract_references(content)

        assert RefType.IMAGE in refs
        assert refs[RefType.IMAGE] == ["/Users/test/photo.png"]

    def test_no_references(self, temp_dir):
        """Test when there are no image references."""
        builder = MessageContentBuilder(temp_dir)
        content = "Just some text without images"

        refs = builder.extract_references(content)

        assert refs == {}

    def test_reference_at_start(self, temp_dir):
        """Test reference at start of content."""
        builder = MessageContentBuilder(temp_dir)
        content = "@:image:photo.png is interesting"

        refs = builder.extract_references(content)

        assert RefType.IMAGE in refs
        assert refs[RefType.IMAGE] == ["photo.png"]

    def test_reference_at_end(self, temp_dir):
        """Test reference at end of content."""
        builder = MessageContentBuilder(temp_dir)
        content = "Look at @:image:photo.png"

        refs = builder.extract_references(content)

        assert RefType.IMAGE in refs
        assert refs[RefType.IMAGE] == ["photo.png"]

    def test_extract_absolute_path(self, temp_dir, create_test_image):
        """Test extracting standalone absolute path to image."""
        builder = MessageContentBuilder(temp_dir)
        image_path = create_test_image("photo")
        content = f"Look at this image: {image_path}"

        refs = builder.extract_references(content)

        assert RefType.IMAGE in refs
        assert str(image_path) in refs[RefType.IMAGE]

    def test_skip_image_references(self, temp_dir, create_test_image):
        """Test that @:image: references are counted separately."""
        builder = MessageContentBuilder(temp_dir)
        image_path = create_test_image("photo")
        content = f"@:image:{image_path} and {image_path}"

        refs = builder.extract_references(content)

        assert RefType.IMAGE in refs
        assert len(refs[RefType.IMAGE]) == 2

    def test_multiple_paths(self, temp_dir, create_test_image):
        """Test extracting multiple standalone paths."""
        builder = MessageContentBuilder(temp_dir)
        img1 = create_test_image("photo1")
        img2 = create_test_image("photo2", ".jpg")
        content = f"Compare {img1} with {img2}"

        refs = builder.extract_references(content)

        assert RefType.IMAGE in refs
        assert str(img1) in refs[RefType.IMAGE]
        assert str(img2) in refs[RefType.IMAGE]

    def test_no_image_paths(self, temp_dir):
        """Test when there are no image paths."""
        builder = MessageContentBuilder(temp_dir)
        content = "Just text without image paths"

        refs = builder.extract_references(content)

        assert refs == {}

    def test_relative_path_rejected(self, temp_dir):
        """Test that relative paths are not extracted."""
        builder = MessageContentBuilder(temp_dir)
        content = "Check out photo.png"

        refs = builder.extract_references(content)

        assert refs == {}


class TestBuild:
    """Tests for build method."""

    def test_build_with_text_and_image(self, temp_dir, create_test_image):
        """Test build with text and one image."""
        builder = MessageContentBuilder(temp_dir)
        image_path = create_test_image("photo")

        content, ref_mapping = builder.build(
            f"Describe this image @:image:{image_path}"
        )

        assert isinstance(content, list)
        assert len(content) == 2
        assert isinstance(content[0], dict) and content[0]["type"] == "text"
        assert (
            isinstance(content[0], dict) and "Describe this image" in content[0]["text"]
        )
        assert isinstance(content[1], dict) and content[1]["type"] == "image"
        assert isinstance(content[1], dict) and content[1]["source_type"] == "base64"

    def test_build_with_multiple_images(self, temp_dir, create_test_image):
        """Test build with multiple images."""
        builder = MessageContentBuilder(temp_dir)
        img1 = create_test_image("photo1")
        img2 = create_test_image("photo2")

        content, ref_mapping = builder.build(
            f"Compare @:image:{img1} and @:image:{img2}"
        )

        assert isinstance(content, list)
        assert len(content) == 3
        assert isinstance(content[0], dict) and content[0]["type"] == "text"
        assert isinstance(content[1], dict) and content[1]["type"] == "image"
        assert isinstance(content[2], dict) and content[2]["type"] == "image"

    def test_build_only_images(self, temp_dir, create_test_image):
        """Test build with only images."""
        builder = MessageContentBuilder(temp_dir)
        image_path = create_test_image("photo")

        content, ref_mapping = builder.build(f"@:image:{image_path}")

        assert isinstance(content, list)
        assert len(content) == 1
        assert isinstance(content[0], dict) and content[0]["type"] == "image"

    def test_build_integration(self, temp_dir, create_test_image):
        """Test build handles whitespace correctly."""
        builder = MessageContentBuilder(temp_dir)
        image_path = create_test_image("photo")

        content, ref_mapping = builder.build(
            f"  \n  Text with whitespace  \n  @:image:{image_path}"
        )

        assert isinstance(content, list)
        text_blocks = [
            b for b in content if isinstance(b, dict) and b.get("type") == "text"
        ]
        assert len(text_blocks) == 1
        assert (
            isinstance(text_blocks[0], dict)
            and "Text with whitespace" in text_blocks[0]["text"]
        )

    def test_build_text_only(self, temp_dir):
        """Test build with text only returns string."""
        builder = MessageContentBuilder(temp_dir)
        content, ref_mapping = builder.build("Just text")

        assert isinstance(content, str)
        assert content == "Just text"
        assert ref_mapping == {}

    def test_build_nonexistent_image_raises_error(self, temp_dir):
        """Test build raises error for non-existent image."""
        import pytest

        builder = MessageContentBuilder(temp_dir)

        with pytest.raises(ValueError, match="Image not found"):
            builder.build("@:image:nonexistent.png")

    def test_build_unsupported_format_raises_error(self, temp_dir):
        """Test build raises error for unsupported image format."""
        import pytest

        # Create a file with unsupported extension
        test_file = temp_dir / "test.txt"
        test_file.write_text("not an image")

        builder = MessageContentBuilder(temp_dir)

        with pytest.raises(ValueError, match="Unsupported format"):
            builder.build(f"@:image:{test_file}")
