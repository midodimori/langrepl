"""Tests for sandbox worker - edge cases."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.sandboxes.worker import execute_tool_async, main, serialize_result


class TestSerializeResult:
    """Tests for result serialization edge cases."""

    def test_tool_message_serialized(self):
        """ToolMessage is properly serialized."""
        from langchain_core.messages import ToolMessage

        msg = ToolMessage(content="tool output", tool_call_id="123", name="test_tool")
        setattr(msg, "short_content", "short")

        result = serialize_result(msg)

        assert result["success"] is True
        assert result["content"] == "tool output"
        assert result["short_content"] == "short"
        assert result["name"] == "test_tool"

    def test_none_result(self):
        """None result is serialized as string."""
        result = serialize_result(None)

        assert result["success"] is True
        assert result["content"] == "None"

    def test_string_result(self):
        """String result is passed through."""
        result = serialize_result("hello world")

        assert result["success"] is True
        assert result["content"] == "hello world"

    def test_large_string_not_truncated(self):
        """Large strings are passed through without truncation."""
        large = "x" * 500000
        result = serialize_result(large)

        assert result["success"] is True
        assert len(result["content"]) == 500000

    def test_command_serialized_with_all_fields(self):
        """Command is properly serialized with all dataclass fields."""
        from langgraph.types import Command

        cmd = Command(goto="next_node", update={"key": "value"}, resume="resume_val")
        result = serialize_result(cmd)

        assert result["success"] is True
        assert result["is_command"] is True
        assert result["goto"] == "next_node"
        assert result["update"] == {"key": "value"}
        assert result["resume"] == "resume_val"
        assert result["graph"] is None  # Default value


class TestExecuteToolAsync:
    """Tests for tool execution edge cases."""

    @pytest.mark.asyncio
    async def test_import_error_returns_structured_error(self):
        """Import errors return structured error, not raise."""
        with patch(
            "src.sandboxes.worker.importlib.import_module",
            side_effect=ModuleNotFoundError("No module named 'nonexistent'"),
        ):
            result = await execute_tool_async("nonexistent.module", "tool", {})

        assert result["success"] is False
        assert "nonexistent" in result["error"]

    @pytest.mark.asyncio
    async def test_missing_tool_returns_error(self):
        """Missing tool attribute returns error, not raise."""
        with patch("src.sandboxes.worker.importlib.import_module") as mock_import:
            mock_module = MagicMock(spec=[])
            mock_import.return_value = mock_module

            result = await execute_tool_async("test.module", "missing_tool", {})

        assert result["success"] is False
        assert "missing_tool" in result["error"]

    @pytest.mark.asyncio
    async def test_non_callable_returns_error(self):
        """Non-callable attribute returns error."""
        with patch("src.sandboxes.worker.importlib.import_module") as mock_import:
            mock_import.return_value = MagicMock(not_callable="just a string")

            result = await execute_tool_async("test.module", "not_callable", {})

        assert result["success"] is False
        assert "Cannot find callable" in result["error"]

    @pytest.mark.asyncio
    async def test_exception_includes_traceback(self):
        """Exceptions include full traceback."""
        mock_tool = MagicMock()
        mock_tool.ainvoke = AsyncMock(side_effect=ValueError("bad value"))
        mock_tool.args_schema = None

        with patch("src.sandboxes.worker.importlib.import_module") as mock_import:
            mock_import.return_value = MagicMock(test_tool=mock_tool)

            result = await execute_tool_async("test.module", "test_tool", {})

        assert result["success"] is False
        assert "bad value" in result["error"]
        assert "traceback" in result
        assert "ValueError" in result["traceback"]

    @pytest.mark.asyncio
    async def test_runtime_injected_when_schema_requires(self):
        """Runtime is injected when tool schema has runtime field."""
        mock_tool = MagicMock()
        mock_tool.ainvoke = AsyncMock(return_value="result")
        mock_tool.args_schema = MagicMock()
        mock_tool.args_schema.model_fields = {
            "runtime": MagicMock(),
            "query": MagicMock(),
        }
        mock_runtime = MagicMock()

        with (
            patch("src.sandboxes.worker.importlib.import_module") as mock_import,
            patch.object(
                __import__("src.sandboxes.worker", fromlist=["create_mock_runtime"]),
                "create_mock_runtime",
                return_value=mock_runtime,
            ),
        ):
            mock_import.return_value = MagicMock(test_tool=mock_tool)

            result = await execute_tool_async(
                "test.module", "test_tool", {"query": "test"}
            )

        assert result["success"] is True
        call_args = mock_tool.ainvoke.call_args[0][0]
        assert call_args["runtime"] is mock_runtime
        assert call_args["query"] == "test"

    @pytest.mark.asyncio
    async def test_async_function_without_invoke(self):
        """Async functions without invoke method work."""

        async def async_func(a, b):
            return f"sum={a + b}"

        with patch("src.sandboxes.worker.importlib.import_module") as mock_import:
            mock_import.return_value = MagicMock(async_func=async_func)

            result = await execute_tool_async(
                "test.module", "async_func", {"a": 1, "b": 2}
            )

        assert result["success"] is True
        assert result["content"] == "sum=3"


class TestMain:
    """Tests for main() entry point edge cases."""

    def test_invalid_json_returns_error(self, capsys):
        """Invalid JSON input returns structured error."""
        with patch("sys.stdin.read", return_value="not valid json"):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["success"] is False
        assert "Invalid JSON" in output["error"]

    def test_missing_module_returns_error(self, capsys):
        """Missing module in request returns error."""
        with patch("sys.stdin.read", return_value='{"tool_name": "test"}'):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["success"] is False
        assert "Missing module or tool_name" in output["error"]

    def test_missing_tool_name_returns_error(self, capsys):
        """Missing tool_name in request returns error."""
        with patch("sys.stdin.read", return_value='{"module": "test.module"}'):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["success"] is False
        assert "Missing module or tool_name" in output["error"]

    def test_empty_args_defaults_to_dict(self, capsys):
        """Args defaults to empty dict when not provided."""
        request = json.dumps({"module": "test.module", "tool_name": "test_tool"})
        captured_args = {}

        async def mock_execute(module_path, tool_name, args):
            captured_args["args"] = args
            return {"success": True, "content": "ok"}

        with (
            patch("sys.stdin.read", return_value=request),
            patch("src.sandboxes.worker.execute_tool_async", mock_execute),
        ):
            main()

        assert captured_args["args"] == {}
