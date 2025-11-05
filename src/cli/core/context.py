"""CLI-specific context dataclass."""

import uuid
from pathlib import Path

from pydantic import BaseModel

from src.cli.bootstrap.initializer import initializer
from src.cli.bootstrap.timer import timer
from src.core.config import ApprovalMode


class Context(BaseModel):
    """Runtime CLI context."""

    agent: str
    model: str
    thread_id: str
    working_dir: Path
    approval_mode: ApprovalMode = ApprovalMode.SEMI_ACTIVE
    current_input_tokens: int | None = None
    current_output_tokens: int | None = None
    total_cost: float | None = None
    context_window: int | None = None
    input_cost_per_mtok: float | None = None
    output_cost_per_mtok: float | None = None
    recursion_limit: int
    tool_output_max_tokens: int | None = None

    @classmethod
    async def create(
        cls,
        agent: str | None,
        model: str | None,
        approval_mode: ApprovalMode | None,
        resume: bool,
        working_dir: Path,
    ) -> "Context":
        """Create context and populate from agent config."""
        with timer("Load agent config"):
            agent_config = await initializer.load_agent_config(agent, working_dir)

        # Get thread_id: resume last thread or create new one
        if resume:
            with timer("Get threads"):
                threads = await initializer.get_threads(
                    agent or agent_config.name, working_dir
                )
            thread_id = threads[0]["thread_id"] if threads else str(uuid.uuid4())
        else:
            thread_id = str(uuid.uuid4())

        if model:
            with timer("Load LLM config"):
                llm_config = await initializer.load_llm_config(model, working_dir)
        else:
            llm_config = agent_config.llm

        return cls(
            agent=agent or agent_config.name,
            model=model or agent_config.llm.alias,
            thread_id=thread_id,
            working_dir=working_dir,
            approval_mode=approval_mode or ApprovalMode.SEMI_ACTIVE,
            context_window=llm_config.context_window,
            input_cost_per_mtok=llm_config.input_cost_per_mtok,
            output_cost_per_mtok=llm_config.output_cost_per_mtok,
            recursion_limit=agent_config.recursion_limit,
            tool_output_max_tokens=agent_config.tool_output_max_tokens,
        )

    def cycle_approval_mode(self) -> ApprovalMode:
        """Cycle to the next approval mode."""
        modes = list(ApprovalMode)
        current_index = modes.index(self.approval_mode)
        next_index = (current_index + 1) % len(modes)
        self.approval_mode = modes[next_index]
        return self.approval_mode
