from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field

from src.core.config import ApprovalMode
from src.skills.factory import Skill


class AgentContext(BaseModel):
    approval_mode: ApprovalMode
    working_dir: Path
    platform: str = Field(default="")
    os_version: str = Field(default="")
    current_date_time_zoned: str = Field(default="")
    user_memory: str = Field(default="")
    tool_catalog: list[BaseTool] = Field(default_factory=list, exclude=True)
    skill_catalog: list[Skill] = Field(default_factory=list, exclude=True)
    input_cost_per_mtok: float | None = None
    output_cost_per_mtok: float | None = None
    tool_output_max_tokens: int | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def template_vars(self) -> dict[str, Any]:
        return {
            "working_dir": str(self.working_dir),
            "platform": self.platform,
            "os_version": self.os_version,
            "current_date_time_zoned": self.current_date_time_zoned,
            "user_memory": self.user_memory,
        }
