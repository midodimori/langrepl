from __future__ import annotations

from typing import TYPE_CHECKING, cast

from langchain.agents.middleware import dynamic_prompt

from src.agents.context import AgentContext
from src.utils.render import render_templates

if TYPE_CHECKING:
    from langchain.agents.middleware import ModelRequest


def create_dynamic_prompt_middleware(template: str):
    @dynamic_prompt
    def render_prompt(request: ModelRequest) -> str:
        if not isinstance(request.runtime.context, AgentContext):
            raise TypeError(
                f"Expected AgentContext, got {type(request.runtime.context)}"
            )
        ctx = cast(AgentContext, request.runtime.context)
        return str(render_templates(template, ctx.template_vars))

    return render_prompt
