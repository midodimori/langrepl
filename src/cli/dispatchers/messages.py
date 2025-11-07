"""Message handling for chat sessions."""

from typing import Any

from langchain_core.messages import AnyMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command, Interrupt

from src.agents.context import AgentContext
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
        """
        Handle a user's message from input through streaming AI response rendering.
        
        Processes the given message by resolving any reference placeholders, packaging it as a human message, creating an agent execution context and runnable configuration, and then streaming the AI response to the session renderer. If processing fails, an error is printed to the console and a debug log is written.
        
        Parameters:
            content (str): The raw user message text (unresolved references).
        """
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
            logger.debug("Message processing error")

    async def _stream_response(
        self,
        input_data: dict[str, Any],
        config: RunnableConfig,
        context: AgentContext,
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
                    context=context,
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
        """
        Process a streaming chunk: update token/cost tracking for each node and render any new messages.
        
        Expects `chunk` in the subgraphs format (a 2-tuple `(namespace, data)`) where `data` is a mapping of node names to node payloads. For each node payload that is a dict, this method updates token and cost fields in the session context and, if the payload contains a non-empty `messages` list, renders the last message. Already-rendered messages are skipped using `rendered_messages`.
        
        Parameters:
            chunk (tuple | dict): A streaming chunk; typically a `(namespace, data)` tuple where `data` maps node names to node payload dicts.
            rendered_messages (set): A set of message identifiers used to avoid rendering the same message more than once.
        """
        if isinstance(chunk, tuple) and len(chunk) == 2:
            # Handle subgraphs=True format: (namespace, data)
            namespace, data = chunk

            # Process different types of updates
            for node_name, node_data in data.items():
                if not isinstance(node_data, dict):
                    continue

                # Update token/cost tracking from any node that has this data
                # (middleware nodes emit these fields first, then get merged into agent state)
                await self._update_token_tracking(node_data)

                # Render messages if present
                if node_data and "messages" in node_data and node_data["messages"]:
                    messages = node_data["messages"]
                    last_message: AnyMessage = messages[-1]

                    message_id = (
                        f"{last_message.id or id(last_message)}_{last_message.type}"
                    )

                    # Skip if we've already rendered this message
                    if message_id in rendered_messages:
                        continue

                    # Mark this message as rendered
                    rendered_messages.add(message_id)

                    # Render the message
                    self.session.renderer.render_message(last_message)

    async def _update_token_tracking(self, node_data: dict[str, Any]) -> None:
        """
        Sync token- and cost-related fields from a node into the session context and trigger an auto-compression check.
        
        If the provided node data contains any of the recognized fields `current_input_tokens`, `current_output_tokens`, or `total_cost`, those values are copied into the session context and an automatic compression decision is evaluated.
        
        Parameters:
            node_data (dict): Node output dictionary that may contain token or cost fields to apply to the session context.
        """
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