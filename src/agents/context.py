from pathlib import Path

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field

from src.core.config import ApprovalMode
from src.skills.factory import Skill


class AgentContext(BaseModel):
    approval_mode: ApprovalMode
    working_dir: Path
    tool_catalog: list[BaseTool] = Field(default_factory=list, exclude=True)
    skill_catalog: list[Skill] = Field(default_factory=list, exclude=True)
    input_cost_per_mtok: float | None = None
    output_cost_per_mtok: float | None = None
    tool_output_max_tokens: int | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)
