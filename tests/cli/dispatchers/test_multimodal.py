"""Tests for multimodal message handling."""

from unittest.mock import AsyncMock, patch

import pytest

from src.cli.dispatchers.messages import MessageDispatcher


class TestBuildContentBlock:
    """Tests for resolver build_content_block method."""

    def test_image_resolver_builds_block(self, create_test_image):
        """Test ImageResolver builds image content block."""
        from src.cli.resolvers.image import ImageResolver

        resolver = ImageResolver()
        image_path = create_test_image("photo")

        block = resolver.build_content_block(str(image_path))

        assert block is not None
        assert block["type"] == "image"
        assert block["source_type"] == "base64"
        assert "data" in block
        assert block["mime_type"] == "image/png"

    def test_image_resolver_invalid_path(self):
        """Test ImageResolver raises FileNotFoundError for invalid path."""
        from src.cli.resolvers.image import ImageResolver

        resolver = ImageResolver()
        with pytest.raises(FileNotFoundError, match="Image not found"):
            resolver.build_content_block("/nonexistent/image.png")

    def test_file_resolver_returns_none(self):
        """Test FileResolver returns None (text-only)."""
        from src.cli.resolvers.file import FileResolver

        resolver = FileResolver()
        block = resolver.build_content_block("/some/file.txt")

        assert block is None


class TestDispatchMultimodal:
    """Integration tests for dispatch method with multimodal content."""

    @pytest.mark.asyncio
    @patch.object(MessageDispatcher, "_stream_response", new_callable=AsyncMock)
    async def test_dispatch_with_image_reference(
        self, mock_stream_response, create_test_image, mock_session
    ):
        """Test dispatching message with @:image: reference."""
        image_path = create_test_image("photo")

        session = mock_session

        dispatcher = MessageDispatcher(session)
        content = f"What's in @:image:{image_path}?"

        await dispatcher.dispatch(content)

        # Verify _stream_response was called with multimodal message
        assert mock_stream_response.called
        call_args = mock_stream_response.call_args
        messages = call_args[0][0]["messages"]
        human_message = messages[0]

        assert isinstance(human_message.content, list)
        assert any(block["type"] == "text" for block in human_message.content)
        assert any(block["type"] == "image" for block in human_message.content)

    @pytest.mark.asyncio
    @patch.object(MessageDispatcher, "_stream_response", new_callable=AsyncMock)
    async def test_dispatch_with_standalone_path(
        self, mock_stream_response, create_test_image, mock_session
    ):
        """Test dispatching message with standalone absolute path."""
        image_path = create_test_image("photo")

        session = mock_session

        dispatcher = MessageDispatcher(session)
        content = f"Analyze this {image_path}"

        await dispatcher.dispatch(content)

        assert mock_stream_response.called
        call_args = mock_stream_response.call_args
        messages = call_args[0][0]["messages"]
        human_message = messages[0]

        assert isinstance(human_message.content, list)
        assert any(block["type"] == "image" for block in human_message.content)

    @pytest.mark.asyncio
    @patch.object(MessageDispatcher, "_stream_response", new_callable=AsyncMock)
    async def test_dispatch_without_images(self, mock_stream_response, mock_session):
        """Test dispatching regular text message without images."""
        session = mock_session

        dispatcher = MessageDispatcher(session)
        content = "Just a regular text message"

        await dispatcher.dispatch(content)

        assert mock_stream_response.called
        call_args = mock_stream_response.call_args
        messages = call_args[0][0]["messages"]
        human_message = messages[0]

        # Should be simple text content, not a list
        assert isinstance(human_message.content, str)
        assert human_message.content == content

    @pytest.mark.asyncio
    @patch.object(MessageDispatcher, "_stream_response", new_callable=AsyncMock)
    async def test_reference_mapping_includes_images(
        self, mock_stream_response, create_test_image, mock_session
    ):
        """Test that reference_mapping includes image paths."""
        image_path = create_test_image("photo")

        session = mock_session

        dispatcher = MessageDispatcher(session)
        content = f"@:image:{image_path}"

        await dispatcher.dispatch(content)

        assert mock_stream_response.called
        call_args = mock_stream_response.call_args
        messages = call_args[0][0]["messages"]
        human_message = messages[0]

        assert "reference_mapping" in human_message.additional_kwargs
        ref_mapping = human_message.additional_kwargs["reference_mapping"]
        assert str(image_path) in ref_mapping
