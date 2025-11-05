"""Tests for command dispatcher."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.cli.dispatchers.commands import CommandDispatcher


class TestCommandDispatcher:
    """Tests for CommandDispatcher class."""

    def test_init_creates_dispatcher(self, mock_session):
        """Test that __init__ creates dispatcher with handlers."""
        dispatcher = CommandDispatcher(mock_session)

        assert dispatcher.session == mock_session
        assert dispatcher.commands is not None
        assert dispatcher.resume_handler is not None
        assert dispatcher.agent_handler is not None
        assert dispatcher.model_handler is not None
        assert dispatcher.mcp_handler is not None
        assert dispatcher.memory_handler is not None
        assert dispatcher.tools_handler is not None
        assert dispatcher.replay_handler is not None
        assert dispatcher.compression_handler is not None
        assert dispatcher.graph_handler is not None

    def test_register_commands_returns_dict(self, mock_session):
        """Test that _register_commands returns command dictionary."""
        dispatcher = CommandDispatcher(mock_session)
        commands = dispatcher._register_commands()

        assert isinstance(commands, dict)
        assert "/help" in commands
        assert "/agents" in commands
        assert "/model" in commands
        assert "/tools" in commands
        assert "/mcp" in commands
        assert "/memory" in commands
        assert "/graph" in commands
        assert "/clear" in commands
        assert "/exit" in commands
        assert "/resume" in commands
        assert "/replay" in commands
        assert "/compress" in commands

    @pytest.mark.asyncio
    async def test_dispatch_with_valid_command(self, mock_session):
        """Test dispatch with valid command."""
        dispatcher = CommandDispatcher(mock_session)
        mock_help = AsyncMock()
        dispatcher.commands["/help"] = mock_help

        await dispatcher.dispatch("/help")

        mock_help.assert_called_once_with([])

    @pytest.mark.asyncio
    async def test_dispatch_with_command_and_args(self, mock_session):
        """Test dispatch with command and arguments."""
        dispatcher = CommandDispatcher(mock_session)
        mock_graph = AsyncMock()
        dispatcher.commands["/graph"] = mock_graph

        await dispatcher.dispatch("/graph --browser")

        mock_graph.assert_called_once_with(["--browser"])

    @pytest.mark.asyncio
    @patch.object(CommandDispatcher, "cmd_help", new_callable=AsyncMock)
    async def test_dispatch_with_invalid_command(self, mock_cmd_help, mock_session):
        """Test dispatch with invalid command shows help."""
        dispatcher = CommandDispatcher(mock_session)

        await dispatcher.dispatch("/invalid")

        mock_cmd_help.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_without_slash_prefix(self, mock_session):
        """Test dispatch without slash prefix returns error."""
        dispatcher = CommandDispatcher(mock_session)

        await dispatcher.dispatch("help")

        # Should not raise exception, just print error

    @pytest.mark.asyncio
    async def test_dispatch_with_empty_command(self, mock_session):
        """Test dispatch with empty command."""
        dispatcher = CommandDispatcher(mock_session)

        await dispatcher.dispatch("/")

        # Should handle gracefully

    @pytest.mark.asyncio
    async def test_dispatch_case_insensitive(self, mock_session):
        """Test dispatch is case insensitive."""
        dispatcher = CommandDispatcher(mock_session)
        mock_help = AsyncMock()
        dispatcher.commands["/help"] = mock_help

        await dispatcher.dispatch("/HELP")

        mock_help.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_with_quoted_args(self, mock_session):
        """Test dispatch handles quoted arguments."""
        dispatcher = CommandDispatcher(mock_session)
        mock_graph = AsyncMock()
        dispatcher.commands["/graph"] = mock_graph

        await dispatcher.dispatch('/graph "--browser"')

        mock_graph.assert_called_once_with(["--browser"])

    @pytest.mark.asyncio
    async def test_cmd_help(self, mock_session):
        """Test cmd_help calls renderer."""
        dispatcher = CommandDispatcher(mock_session)
        mock_session.renderer = MagicMock()

        await dispatcher.cmd_help([])

        mock_session.renderer.render_help.assert_called_once_with(dispatcher.commands)

    @pytest.mark.asyncio
    @patch.object(CommandDispatcher, "agent_handler", create=True)
    async def test_cmd_agents(self, mock_agent_handler, mock_session):
        """Test cmd_agents delegates to agent handler."""
        dispatcher = CommandDispatcher(mock_session)
        dispatcher.agent_handler = mock_agent_handler
        mock_agent_handler.handle = AsyncMock()

        await dispatcher.cmd_agents([])

        mock_agent_handler.handle.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(CommandDispatcher, "model_handler", create=True)
    async def test_cmd_model(self, mock_model_handler, mock_session):
        """Test cmd_model delegates to model handler."""
        dispatcher = CommandDispatcher(mock_session)
        dispatcher.model_handler = mock_model_handler
        mock_model_handler.handle = AsyncMock()

        await dispatcher.cmd_model([])

        mock_model_handler.handle.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(CommandDispatcher, "tools_handler", create=True)
    @patch("src.cli.dispatchers.commands.initializer")
    async def test_cmd_tools(
        self,
        mock_initializer_patch,
        mock_tools_handler,
        mock_session,
    ):
        """Test cmd_tools delegates to tools handler."""
        dispatcher = CommandDispatcher(mock_session)
        dispatcher.tools_handler = mock_tools_handler
        mock_tools_handler.handle = AsyncMock()
        mock_initializer_patch.cached_tools = ["tool1", "tool2"]

        await dispatcher.cmd_tools([])

        mock_tools_handler.handle.assert_called_once_with(["tool1", "tool2"])

    @pytest.mark.asyncio
    @patch.object(CommandDispatcher, "mcp_handler", create=True)
    async def test_cmd_mcp(self, mock_mcp_handler, mock_session):
        """Test cmd_mcp delegates to mcp handler."""
        dispatcher = CommandDispatcher(mock_session)
        dispatcher.mcp_handler = mock_mcp_handler
        mock_mcp_handler.handle = AsyncMock()

        await dispatcher.cmd_mcp([])

        mock_mcp_handler.handle.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(CommandDispatcher, "memory_handler", create=True)
    async def test_cmd_memory(self, mock_memory_handler, mock_session):
        """Test cmd_memory delegates to memory handler."""
        dispatcher = CommandDispatcher(mock_session)
        dispatcher.memory_handler = mock_memory_handler
        mock_memory_handler.handle = AsyncMock()

        await dispatcher.cmd_memory([])

        mock_memory_handler.handle.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.cli.dispatchers.commands.console.clear")
    async def test_cmd_clear(self, mock_clear, mock_session, mock_context):
        """Test cmd_clear creates new thread and clears screen."""
        mock_session.context = mock_context
        dispatcher = CommandDispatcher(mock_session)
        original_thread_id = mock_context.thread_id

        await dispatcher.cmd_clear([])

        mock_clear.assert_called_once()
        # Verify update_context was called with new thread_id
        mock_session.update_context.assert_called_once()
        call_kwargs = mock_session.update_context.call_args[1]
        assert "thread_id" in call_kwargs
        assert call_kwargs["thread_id"] != original_thread_id

    @pytest.mark.asyncio
    async def test_cmd_exit(self, mock_session):
        """Test cmd_exit sets running to False."""
        dispatcher = CommandDispatcher(mock_session)
        mock_session.running = True

        await dispatcher.cmd_exit([])

        assert mock_session.running is False

    @pytest.mark.asyncio
    @patch.object(CommandDispatcher, "resume_handler", create=True)
    async def test_cmd_resume(self, mock_resume_handler, mock_session):
        """Test cmd_resume delegates to resume handler."""
        dispatcher = CommandDispatcher(mock_session)
        dispatcher.resume_handler = mock_resume_handler
        mock_resume_handler.handle = AsyncMock()

        await dispatcher.cmd_resume([])

        mock_resume_handler.handle.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(CommandDispatcher, "replay_handler", create=True)
    async def test_cmd_replay(self, mock_replay_handler, mock_session):
        """Test cmd_replay delegates to replay handler."""
        dispatcher = CommandDispatcher(mock_session)
        dispatcher.replay_handler = mock_replay_handler
        mock_replay_handler.handle = AsyncMock()

        await dispatcher.cmd_replay([])

        mock_replay_handler.handle.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(CommandDispatcher, "compression_handler", create=True)
    async def test_cmd_compress(self, mock_compression_handler, mock_session):
        """Test cmd_compress delegates to compression handler."""
        dispatcher = CommandDispatcher(mock_session)
        dispatcher.compression_handler = mock_compression_handler
        mock_compression_handler.handle = AsyncMock()

        await dispatcher.cmd_compress([])

        mock_compression_handler.handle.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(CommandDispatcher, "graph_handler", create=True)
    async def test_cmd_graph_without_args(self, mock_graph_handler, mock_session):
        """Test cmd_graph without arguments."""
        dispatcher = CommandDispatcher(mock_session)
        dispatcher.graph_handler = mock_graph_handler
        mock_graph_handler.handle = AsyncMock()

        await dispatcher.cmd_graph([])

        mock_graph_handler.handle.assert_called_once_with(open_browser=False)

    @pytest.mark.asyncio
    @patch.object(CommandDispatcher, "graph_handler", create=True)
    async def test_cmd_graph_with_browser_flag(self, mock_graph_handler, mock_session):
        """Test cmd_graph with --browser flag."""
        dispatcher = CommandDispatcher(mock_session)
        dispatcher.graph_handler = mock_graph_handler
        mock_graph_handler.handle = AsyncMock()

        await dispatcher.cmd_graph(["--browser"])

        mock_graph_handler.handle.assert_called_once_with(open_browser=True)

    @pytest.mark.asyncio
    @patch.object(CommandDispatcher, "graph_handler", create=True)
    async def test_cmd_graph_with_invalid_args(self, mock_graph_handler, mock_session):
        """Test cmd_graph with invalid arguments."""
        dispatcher = CommandDispatcher(mock_session)
        dispatcher.graph_handler = mock_graph_handler
        mock_graph_handler.handle = AsyncMock()

        await dispatcher.cmd_graph(["--invalid"])

        # Should not call handler, just print error
        mock_graph_handler.handle.assert_not_called()

    @pytest.mark.asyncio
    @patch.object(
        CommandDispatcher,
        "cmd_help",
        new_callable=AsyncMock,
        side_effect=Exception("Test error"),
    )
    async def test_dispatch_handles_exceptions(self, mock_cmd_help, mock_session):
        """Test dispatch handles exceptions gracefully."""
        dispatcher = CommandDispatcher(mock_session)

        # Should not raise, just print error
        await dispatcher.dispatch("/help")
