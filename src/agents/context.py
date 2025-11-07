from pathlib import Path

from pydantic import BaseModel

from src.core.config import ApprovalMode


class AgentContext(BaseModel):
    """Runtime context for agent execution."""

    approval_mode: ApprovalMode
    working_dir: Path
    input_cost_per_mtok: float | None = None
    output_cost_per_mtok: float | None = None
    tool_output_max_tokens: int | None = None
