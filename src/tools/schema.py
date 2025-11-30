from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from pydantic import BaseModel, create_model

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool


class ToolSchema(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any] | None = None

    @classmethod
    def from_tool(cls, tool: BaseTool) -> ToolSchema:
        args_schema = tool.args_schema
        if not args_schema:
            parameters = {"type": "object", "properties": {}}
        elif isinstance(args_schema, dict):
            parameters = args_schema
        else:
            filtered_fields: dict[str, Any] = {
                name: (field.annotation, field)
                for name, field in args_schema.model_fields.items()
                if name != "runtime"
            }
            user_schema = create_model(
                f"{tool.name}Args", **cast(dict[str, Any], filtered_fields)
            )
            parameters = user_schema.model_json_schema()

        return cls(
            name=tool.name,
            description=tool.description,
            parameters=parameters,
        )


def parameters_to_model(
    name: str, parameters: dict[str, Any] | None
) -> type[BaseModel] | None:
    """Convert stored parameters JSON schema into a permissive pydantic model.

    JSON Schema validation is handled separately; this model satisfies BaseTool.args_schema.
    """
    if not parameters:
        return None

    properties = parameters.get("properties")
    if not isinstance(properties, dict):
        return None

    field_defs: dict[str, Any] = {
        field_name: (Any, ...)
        for field_name, schema in properties.items()
        if isinstance(schema, dict)
    }

    return create_model(f"{name}Args", **cast(dict[str, Any], field_defs))
