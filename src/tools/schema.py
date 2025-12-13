from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool


class ToolSchema(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any] | None = None

    @classmethod
    def from_tool(cls, tool: BaseTool) -> ToolSchema:
        schema = tool.tool_call_schema
        if isinstance(schema, dict):
            parameters = schema
        elif schema is not None:
            parameters = schema.model_json_schema()
        else:
            parameters = {"type": "object", "properties": {}}

        return cls(
            name=tool.name,
            description=tool.description,
            parameters=parameters,
        )
