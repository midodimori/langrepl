"""Message handling for chat sessions."""

from typing import Any

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command, Interrupt

from src.cli.bootstrap.initializer import initializer
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

    async def dispatch(self, content: str) -> None:
        """Dispatch user message and get AI response."""
        try:
            reference_mapping = self.session.prefilled_reference_mapping.copy()
            self.session.prefilled_reference_mapping.clear()

            resolved_content = self.session.prompt.completer.resolve_refs(content)

            human_message = HumanMessage(
                content=resolved_content,
                short_content=content,
                additional_kwargs={"reference_mapping": reference_mapping},
            )

            # Prepare graph config
            ctx = self.session.context
            config_dict = {
                "thread_id": ctx.thread_id,
                "approval_mode": ctx.approval_mode.value,
                "working_dir": ctx.working_dir,
                "input_cost_per_mtok": ctx.input_cost_per_mtok,
                "output_cost_per_mtok": ctx.output_cost_per_mtok,
                "tool_output_max_tokens": ctx.tool_output_max_tokens,
            }

            graph_config = RunnableConfig(
                configurable=config_dict,
                recursion_limit=ctx.recursion_limit,
            )

            await self._stream_response(
                {"messages": [human_message]},
                graph_config,
            )

        except Exception as e:
            console.print_error(f"Error processing message: {e}")
            logger.debug("Message processing error")

    async def _stream_response(
        self,
        input_data: dict[str, Any],
        config: RunnableConfig,
    ) -> None:
        """Stream with automatic interrupt handling loop."""
        current_input: dict[str, Any] | Command = input_data
        rendered_messages: set[str] = set()

        while True:
            interrupted = False
            with console.console.status(
                f"[{theme.spinner_color}]Randomizing...[/{theme.spinner_color}]"
            ) as status:
                async for chunk in self.session.graph.astream(
                    current_input,
                    config,
                    stream_mode="updates",
                    subgraphs=True,
                ):
                    interrupts = self._extract_interrupts(chunk)
                    if interrupts:
                        # Stop spinner before handling interrupt
                        status.stop()
                        # Handle interrupt and prepare next iteration
                        resume_value = await self.interrupt_handler.handle(interrupts)
                        current_input = Command(resume=resume_value)
                        interrupted = True
                        break  # Break inner loop, continue outer while loop
                    else:
                        await self._process_chunk(chunk, rendered_messages)

            if not interrupted:
                # No interrupts encountered, streaming completed
                break

    @staticmethod
    def _extract_interrupts(chunk) -> list[Interrupt] | None:
        """Extract interrupt data from chunk."""
        if isinstance(chunk, tuple) and len(chunk) == 2:
            _, data = chunk
            return data["__interrupt__"] if "__interrupt__" in data else None
        elif isinstance(chunk, dict):
            return chunk["__interrupt__"] if "__interrupt__" in chunk else None
        return None

    async def _process_chunk(self, chunk, rendered_messages) -> None:
        """Process a streaming chunk and display separate blocks."""
        if isinstance(chunk, tuple) and len(chunk) == 2:
            # Handle subgraphs=True format: (namespace, data)
            namespace, data = chunk

            # Process different types of updates
            for node_name, node_data in data.items():
                if node_data and "messages" in node_data and node_data["messages"]:
                    messages = node_data["messages"]
                    last_message: AnyMessage = messages[-1]

                    message_id = (
                        f"{last_message.id or id(last_message)}_{last_message.type}"
                    )

                    # Skip if we've already rendered this message
                    if message_id in rendered_messages:
                        return

                    # Mark this message as rendered
                    rendered_messages.add(message_id)

                    # Render the message
                    self.session.renderer.render_message(last_message)

                    # Sync context from state (updated by agent)
                    if isinstance(last_message, AIMessage):
                        self.session.update_context(
                            current_input_tokens=node_data.get("current_input_tokens"),
                            current_output_tokens=node_data.get(
                                "current_output_tokens"
                            ),
                            total_cost=node_data.get("total_cost"),
                        )

                        # Check for auto-compression
                        await self._check_auto_compression()

    async def _check_auto_compression(self) -> None:
        """Check if auto-compression should be triggered and execute if needed."""
        try:
            ctx = self.session.context
            config_data = await initializer.load_agents_config(ctx.working_dir)
            agent_config = config_data.get_agent_config(ctx.agent)

            if not agent_config or not agent_config.compression:
                return

            compression_config = agent_config.compression

            if not compression_config.auto_compress_enabled:
                return

            context_window = agent_config.llm.context_window
            current_tokens = ctx.current_input_tokens or 0

            if should_auto_compress(
                current_tokens,
                context_window,
                compression_config.auto_compress_threshold,
            ):
                usage_pct = int(
                    (current_tokens / context_window * 100) if context_window else 0
                )

                with console.console.status(
                    f"[{theme.spinner_color}]Context at {usage_pct}%, auto-compressing to new thread...[/{theme.spinner_color}]"
                ):
                    compression_handler = CompressionHandler(self.session)
                    await compression_handler.handle()

        except Exception as e:
            logger.debug(f"Auto-compression check failed: {e}", exc_info=True)
