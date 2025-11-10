"""Tests for multimodal message handling."""

import base64
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.cli.dispatchers.messages import MessageDispatcher
from src.core.config import ApprovalMode


@pytest.fixture
def create_test_image(tmp_path):
    """Create a minimal test PNG image."""

    def _create(filename: str = "test.png") -> Path:
        # Minimal 1x1 PNG image
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        image_path = tmp_path / filename
        image_path.write_bytes(png_data)
        return image_path

    return _create


@pytest.fixture
def mock_session():
    """Create a mock session for MessageDispatcher."""
    session = MagicMock()
    session.prefilled_reference_mapping = {}
    session.context.approval_mode = ApprovalMode.SEMI_ACTIVE
    session.context.working_dir = "/test/dir"
    session.context.thread_id = "test-thread"
    session.context.recursion_limit = 100
    session.context.input_cost_per_mtok = 0.01
    session.context.output_cost_per_mtok = 0.03
    session.context.tool_output_max_tokens = 5000
    session.graph = MagicMock()
    session.graph.astream = AsyncMock(return_value=iter([]))
    return session


class TestBuildContentBlock:
    """Tests for resolver build_content_block method."""

    def test_image_resolver_builds_block(self, create_test_image):
        """Test ImageResolver builds image content block."""
        from src.cli.resolvers.image import ImageResolver

        resolver = ImageResolver()
        image_path = create_test_image("photo.png")

        block = resolver.build_content_block(str(image_path))

        assert block is not None
        assert block["type"] == "image"
        assert block["source_type"] == "base64"
        assert "data" in block
        assert block["mime_type"] == "image/png"

    def test_image_resolver_invalid_path(self):
        """Test ImageResolver returns None for invalid path."""
        from src.cli.resolvers.image import ImageResolver

        resolver = ImageResolver()
        block = resolver.build_content_block("/nonexistent/image.png")

        assert block is None

    def test_file_resolver_returns_none(self):
        """Test FileResolver returns None (text-only)."""
        from src.cli.resolvers.file import FileResolver

        resolver = FileResolver()
        block = resolver.build_content_block("/some/file.txt")

        assert block is None


class TestDispatchMultimodal:
    """Integration tests for dispatch method with multimodal content."""

    @pytest.mark.asyncio
    async def test_dispatch_with_image_reference(self, tmp_path, create_test_image):
        """Test dispatching message with @:image: reference."""
        image_path = create_test_image("photo.png")

        # Create session with proper working directory
        session = MagicMock()
        session.prefilled_reference_mapping = {}
        session.context.approval_mode = ApprovalMode.SEMI_ACTIVE
        session.context.working_dir = str(tmp_path)
        session.context.thread_id = "test-thread"
        session.context.recursion_limit = 100
        session.context.input_cost_per_mtok = 0.01
        session.context.output_cost_per_mtok = 0.03
        session.context.tool_output_max_tokens = 5000
        session.graph = MagicMock()
        session.graph.astream = AsyncMock(return_value=iter([]))

        dispatcher = MessageDispatcher(session)
        content = f"What's in @:image:{image_path}?"

        mock_stream_response = AsyncMock()
        with patch.object(dispatcher, "_stream_response", mock_stream_response):
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
    async def test_dispatch_with_standalone_path(self, tmp_path, create_test_image):
        """Test dispatching message with standalone absolute path."""
        image_path = create_test_image("photo.png")

        # Create session with proper working directory
        session = MagicMock()
        session.prefilled_reference_mapping = {}
        session.context.approval_mode = ApprovalMode.SEMI_ACTIVE
        session.context.working_dir = str(tmp_path)
        session.context.thread_id = "test-thread"
        session.context.recursion_limit = 100
        session.context.input_cost_per_mtok = 0.01
        session.context.output_cost_per_mtok = 0.03
        session.context.tool_output_max_tokens = 5000
        session.graph = MagicMock()
        session.graph.astream = AsyncMock(return_value=iter([]))

        dispatcher = MessageDispatcher(session)
        content = f"Analyze this {image_path}"

        mock_stream_response = AsyncMock()
        with patch.object(dispatcher, "_stream_response", mock_stream_response):
            await dispatcher.dispatch(content)

        assert mock_stream_response.called
        call_args = mock_stream_response.call_args
        messages = call_args[0][0]["messages"]
        human_message = messages[0]

        assert isinstance(human_message.content, list)
        assert any(block["type"] == "image" for block in human_message.content)

    @pytest.mark.asyncio
    async def test_dispatch_without_images(self, tmp_path):
        """Test dispatching regular text message without images."""
        # Create session with proper working directory
        session = MagicMock()
        session.prefilled_reference_mapping = {}
        session.context.approval_mode = ApprovalMode.SEMI_ACTIVE
        session.context.working_dir = str(tmp_path)
        session.context.thread_id = "test-thread"
        session.context.recursion_limit = 100
        session.context.input_cost_per_mtok = 0.01
        session.context.output_cost_per_mtok = 0.03
        session.context.tool_output_max_tokens = 5000
        session.graph = MagicMock()
        session.graph.astream = AsyncMock(return_value=iter([]))

        dispatcher = MessageDispatcher(session)
        content = "Just a regular text message"

        mock_stream_response = AsyncMock()
        with patch.object(dispatcher, "_stream_response", mock_stream_response):
            await dispatcher.dispatch(content)

        assert mock_stream_response.called
        call_args = mock_stream_response.call_args
        messages = call_args[0][0]["messages"]
        human_message = messages[0]

        # Should be simple text content, not a list
        assert isinstance(human_message.content, str)
        assert human_message.content == content

    @pytest.mark.asyncio
    async def test_reference_mapping_includes_images(self, tmp_path, create_test_image):
        """Test that reference_mapping includes image paths."""
        image_path = create_test_image("photo.png")

        # Create session with proper working directory
        session = MagicMock()
        session.prefilled_reference_mapping = {}
        session.context.approval_mode = ApprovalMode.SEMI_ACTIVE
        session.context.working_dir = str(tmp_path)
        session.context.thread_id = "test-thread"
        session.context.recursion_limit = 100
        session.context.input_cost_per_mtok = 0.01
        session.context.output_cost_per_mtok = 0.03
        session.context.tool_output_max_tokens = 5000
        session.graph = MagicMock()
        session.graph.astream = AsyncMock(return_value=iter([]))

        dispatcher = MessageDispatcher(session)
        content = f"@:image:{image_path}"

        mock_stream_response = AsyncMock()
        with patch.object(dispatcher, "_stream_response", mock_stream_response):
            await dispatcher.dispatch(content)

        assert mock_stream_response.called
        call_args = mock_stream_response.call_args
        messages = call_args[0][0]["messages"]
        human_message = messages[0]

        assert "reference_mapping" in human_message.additional_kwargs
        ref_mapping = human_message.additional_kwargs["reference_mapping"]
        assert str(image_path) in ref_mapping
