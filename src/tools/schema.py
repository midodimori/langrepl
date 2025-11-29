from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, create_model


class ToolSchema(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any] | None = None

    @classmethod
    def from_tool(cls, tool: BaseTool) -> "ToolSchema":
        args_schema = tool.args_schema
        if not args_schema:
            parameters = {"type": "object", "properties": {}}
        elif isinstance(args_schema, dict):
            parameters = args_schema
        else:
            fields_to_include: dict[str, Any] = {}
            for name, field in args_schema.model_fields.items():
                if name == "runtime":
                    continue

                if field.default_factory:
                    field_obj = Field(
                        default_factory=field.default_factory,
                        description=field.description,
                        title=field.title,
                    )
                elif not field.is_required():
                    field_obj = Field(
                        default=field.default,
                        description=field.description,
                        title=field.title,
                    )
                else:
                    field_obj = Field(
                        description=field.description,
                        title=field.title,
                    )
                fields_to_include[name] = (field.annotation, field_obj)

            user_schema = create_model(f"{tool.name}Args", **fields_to_include)
            parameters = user_schema.model_json_schema()

        return cls(
            name=tool.name,
            description=tool.description,
            parameters=parameters,
        )
