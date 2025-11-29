from typing import cast

from langchain.agents.middleware import ModelRequest, dynamic_prompt

from src.agents.context import AgentContext
from src.utils.render import render_templates


def create_dynamic_prompt_middleware(template: str):
    @dynamic_prompt
    def render_prompt(request: ModelRequest) -> str:
        ctx = cast(AgentContext, request.runtime.context)
        return str(render_templates(template, ctx.template_vars))

    return render_prompt
