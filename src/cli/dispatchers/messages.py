"""Message handling for chat sessions."""

import asyncio
import hashlib
from pathlib import Path
from typing import Any

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    AnyMessage,
    HumanMessage,
    ToolMessage,
)
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command, Interrupt
from rich.console import Group
from rich.markup import render
from rich.text import Text

from src.agents.context import AgentContext
from src.cli.bootstrap.initializer import initializer
from src.cli.builders import MessageContentBuilder
from src.cli.handlers import CompressionHandler, InterruptHandler
from src.cli.theme import console, theme
from src.core.logging import get_logger
from src.utils.compression import should_auto_compress

logger = get_logger(__name__)


class MessageDispatcher:
    """Dispatch user message processing and AI response streaming."""

    def __init__(self, session):
        """Initialize with reference to CLI session."""
        self.session = session
        self.interrupt_handler = InterruptHandler()
        self.message_builder = MessageContentBuilder(Path(session.context.working_dir))
        self._pending_compression = False

    async def dispatch(self, content: str) -> None:
        """Dispatch user message and get AI response."""
        try:
            reference_mapping = self.session.prefilled_reference_mapping.copy()
            self.session.prefilled_reference_mapping.clear()

            message_content, image_refs = self.message_builder.build(content)

            reference_mapping.update(image_refs)

            human_message = HumanMessage(
                content=message_content,
                short_content=content,
                additional_kwargs={"reference_mapping": reference_mapping},
            )
            ctx = self.session.context
            agent_context = AgentContext(
                approval_mode=ctx.approval_mode,
                working_dir=ctx.working_dir,
                input_cost_per_mtok=ctx.input_cost_per_mtok,
                output_cost_per_mtok=ctx.output_cost_per_mtok,
                tool_output_max_tokens=ctx.tool_output_max_tokens,
            )

            graph_config = RunnableConfig(
                configurable={"thread_id": ctx.thread_id},
                recursion_limit=ctx.recursion_limit,
            )

            await self._stream_response(
                {"messages": [human_message]},
                graph_config,
                agent_context,
            )

        except Exception as e:
            console.print_error(f"Error processing message: {e}")
            console.print("")
            logger.debug("Message processing error", exc_info=True)

    async def _stream_response(
        self,
        input_data: dict[str, Any],
        config: RunnableConfig,
        context: AgentContext,
    ) -> None:
        """Stream with automatic interrupt handling loop."""
        self._pending_compression = False
        current_input: dict[str, Any] | Command = input_data
        rendered_messages: set[str] = set()
        streaming_state: dict[str, Any] = {
            "active": False,
            "message_id": None,
            "preview_lines": [""],
            "chunks": [],
        }

        while True:
            interrupted = False
            cancelled = False

            try:
                with console.console.status(
                    f"[{theme.spinner_color}]Randomizing...[/{theme.spinner_color}]"
                ) as status:
                    async for chunk in self.session.graph.astream(
                        current_input,
                        config,
                        context=context,
                        stream_mode=["messages", "updates"],
                        subgraphs=True,
                    ):
                        interrupts = self._extract_interrupts(chunk)
                        if interrupts:
                            self._clear_preview(streaming_state)
                            status.stop()
                            resume_value = await self.interrupt_handler.handle(
                                interrupts
                            )
                            if isinstance(resume_value, dict):
                                current_input = Command(resume=resume_value)
                            else:
                                current_input = Command(
                                    resume={interrupts[0].id: resume_value}
                                )
                            interrupted = True
                            break

                        _namespace, mode, data = chunk
                        if mode == "messages":
                            await self._process_message_chunk(
                                data, streaming_state, status, rendered_messages
                            )
                        elif mode == "updates":
                            self._finalize_streaming(
                                streaming_state, None, rendered_messages
                            )
                            await self._process_update_chunk(data, rendered_messages)

            except (asyncio.CancelledError, KeyboardInterrupt):
                self._finalize_streaming(streaming_state, None, rendered_messages)
                cancelled = True

            if cancelled or not interrupted:
                self._finalize_streaming(streaming_state, None, rendered_messages)
                break

        if self._pending_compression and not cancelled:
            self._pending_compression = False
            try:
                await self._execute_compression()
            except (asyncio.CancelledError, KeyboardInterrupt):
                pass

    @staticmethod
    def _extract_interrupts(chunk) -> list[Interrupt] | None:
        """Extract interrupt data from chunk."""
        if isinstance(chunk, tuple) and len(chunk) == 3:
            _namespace, _mode, data = chunk
            if isinstance(data, dict):
                return data.get("__interrupt__")
        elif isinstance(chunk, dict):
            return chunk.get("__interrupt__")
        return None

    @staticmethod
    def _get_stable_message_id(message: AnyMessage) -> str:
        """Get a stable ID for deduplication, even when message.id is None.

        Returns a base ID without type suffix. Caller should append type if needed.
        """
        if message.id:
            return message.id

        content_str = str(message.content) if message.content else ""
        stable_key = hashlib.sha256(
            f"{content_str}:{message.type}".encode()
        ).hexdigest()[:8]
        return stable_key

    async def _process_message_chunk(
        self,
        data: tuple[AnyMessage, dict],
        streaming_state: dict,
        status,
        rendered_messages: set[str],
    ) -> None:
        """Process message chunk for token-by-token streaming preview."""
        message_chunk, _metadata = data

        if isinstance(message_chunk, AIMessageChunk):
            message_id = self._get_stable_message_id(message_chunk)

            if (
                not streaming_state["active"]
                or streaming_state["message_id"] != message_id
            ):
                self._finalize_streaming(streaming_state, None, rendered_messages)
                streaming_state["active"] = True
                streaming_state["message_id"] = message_id
                streaming_state["preview_lines"] = [""]
                streaming_state["chunks"] = []

            streaming_state["chunks"].append(message_chunk)

            content = self._extract_chunk_content(message_chunk)
            if content:
                lines = content.split("\n")
                if len(lines) == 1:
                    streaming_state["preview_lines"][-1] += lines[0]
                else:
                    streaming_state["preview_lines"][-1] += lines[0]
                    for new_line in lines[1:]:
                        streaming_state["preview_lines"].append(new_line)
                    if len(streaming_state["preview_lines"]) > 4:
                        streaming_state["preview_lines"] = streaming_state[
                            "preview_lines"
                        ][-4:]

                window_preview = "\n".join(streaming_state["preview_lines"][-3:])

                spinner_text = render(
                    f"[{theme.spinner_color}]Randomizing...[/{theme.spinner_color}]"
                )
                status.update(Group(spinner_text, Text(window_preview, style="dim")))

    async def _process_update_chunk(
        self, data: dict, rendered_messages: set[str]
    ) -> None:
        """Process update chunk for tools/state (batch mode)."""
        for _node_name, node_data in data.items():
            if not isinstance(node_data, dict):
                continue

            await self._update_token_tracking(node_data)

            if node_data and "messages" in node_data and node_data["messages"]:
                messages = node_data["messages"]
                last_message: AnyMessage = messages[-1]
                base_id = self._get_stable_message_id(last_message)
                message_id = f"{base_id}_{last_message.type}"

                if message_id in rendered_messages:
                    continue

                rendered_messages.add(message_id)

                if isinstance(last_message, (AIMessage, ToolMessage)):
                    self.session.renderer.render_message(last_message)

    @staticmethod
    def _extract_chunk_content(chunk: AIMessageChunk) -> str:
        """Extract text content from AI message chunk."""
        if isinstance(chunk.content, str):
            return chunk.content
        elif isinstance(chunk.content, list):
            texts = []
            for block in chunk.content:
                if isinstance(block, str):
                    texts.append(block)
                elif isinstance(block, dict) and block.get("type") == "text":
                    texts.append(block.get("text", ""))
            return "".join(texts)
        return ""

    @staticmethod
    def _clear_preview(streaming_state: dict) -> None:
        """Clear preview without rendering final message."""
        if streaming_state["active"]:
            streaming_state["active"] = False
            streaming_state["message_id"] = None
            streaming_state["preview_lines"] = [""]
            streaming_state["chunks"] = []

    def _finalize_streaming(
        self, streaming_state: dict, status, rendered_messages: set[str]
    ) -> None:
        """Finalize active streaming message and render final version."""
        if streaming_state["active"]:
            if status:
                status.stop()

            if streaming_state["chunks"]:
                final_message = self._merge_chunks(streaming_state["chunks"])
                self.session.renderer.render_assistant_message(final_message)
                message_id = f"{streaming_state['message_id']}_{final_message.type}"
                rendered_messages.add(message_id)

            self._clear_preview(streaming_state)

    @staticmethod
    def _merge_chunks(chunks: list[AIMessageChunk]) -> AIMessage:
        """Merge message chunks into final AIMessage, preserving all attributes."""
        if not chunks:
            return AIMessage(content="")

        merged = chunks[0]
        for chunk in chunks[1:]:
            merged = merged + chunk

        return AIMessage(
            content=merged.content,
            additional_kwargs=merged.additional_kwargs,
            response_metadata=merged.response_metadata,
            tool_calls=merged.tool_calls,
            id=merged.id,
            name=merged.name,
        )

    async def _update_token_tracking(self, node_data: dict[str, Any]) -> None:
        """Update session context with token tracking data if present in node."""
        token_fields = {
            "current_input_tokens",
            "current_output_tokens",
            "total_cost",
        }

        # Check if any token tracking fields are present
        if not any(field in node_data for field in token_fields):
            return

        # Extract and update context
        updates = {
            field: node_data.get(field) for field in token_fields if field in node_data
        }

        if updates:
            self.session.update_context(**updates)
            # Check if auto-compression should be triggered after token update
            await self._check_auto_compression()

    async def _check_auto_compression(self) -> None:
        """Check if auto-compression should be triggered."""
        try:
            ctx = self.session.context
            config_data = await initializer.load_agents_config(ctx.working_dir)
            agent_config = config_data.get_agent_config(ctx.agent)

            if (
                agent_config
                and agent_config.compression
                and agent_config.compression.auto_compress_enabled
                and should_auto_compress(
                    ctx.current_input_tokens or 0,
                    ctx.context_window,
                    agent_config.compression.auto_compress_threshold,
                )
            ):
                self._pending_compression = True

        except Exception as e:
            logger.warning(f"Auto-compression check failed: {e}", exc_info=True)

    async def _execute_compression(self) -> None:
        """Execute compression after streaming completes."""
        ctx = self.session.context
        usage_pct = int(
            (ctx.current_input_tokens or 0) / ctx.context_window * 100
            if ctx.context_window
            else 0
        )

        with console.console.status(
            f"[{theme.spinner_color}]Context at {usage_pct}%, auto-compressing to new thread...[/{theme.spinner_color}]"
        ):
            await CompressionHandler(self.session).handle()
