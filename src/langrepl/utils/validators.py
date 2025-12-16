"""Reusable Pydantic validators for tools."""

import inspect
import json
from collections.abc import Callable
from typing import Annotated, Any, get_args, get_origin

from json_repair import repair_json
from langchain.tools import tool
from pydantic import BaseModel, ConfigDict, Field, create_model, field_validator
from pydantic.fields import FieldInfo


def json_list_parser(model_cls: type[BaseModel]):
    """Parse JSON strings into list of models (handles LLM serialization bugs)."""

    def validator(v: Any) -> Any:
        if not isinstance(v, str):
            return v

        try:
            parsed = json.loads(v)
        except (json.JSONDecodeError, ValueError) as e:
            try:
                parsed = json.loads(repair_json(v))
            except Exception:
                raise ValueError(
                    f"Failed to parse JSON (auto-repair failed): {e}"
                ) from e

        if not isinstance(parsed, list):
            raise TypeError(
                f"Expected JSON array for {model_cls.__name__}, "
                f"got {type(parsed).__name__}: {parsed}"
            )

        return [model_cls.model_validate(item) for item in parsed]

    return validator


def _resolve_default(param: inspect.Parameter, field_info: Any) -> Any:
    """Resolve default value from field_info or parameter default."""
    if field_info and hasattr(field_info, "is_required"):
        # Field exists - check if it needs param's default
        if field_info.is_required() and param.default != inspect.Parameter.empty:
            # Field has no default but param does - merge them
            return Field(
                default=param.default,
                description=field_info.description,
                title=field_info.title,
            )
        return field_info
    return ... if param.default == inspect.Parameter.empty else param.default


def json_safe_tool(func: Callable) -> Any:
    """Decorator that wraps @tool and auto-handles JSON string parsing for list[Model] params.

    IMPORTANT: Use Annotated[T, Field(description=...)] for all parameters to ensure
    descriptions appear in catalog schema. Docstring Args sections are not used when
    custom args_schema is provided.

    Usage:
        from typing import Annotated
        from pydantic import Field

        @json_safe_tool
        async def my_tool(
            items: Annotated[list[Item], Field(description="List of items")],
            name: Annotated[str, Field(description="The name")],
            runtime: ToolRuntime
        ) -> str:
            # Tool description in docstring
            ...
    """
    sig = inspect.signature(func)
    fields: dict[str, Any] = {}
    validators: dict[str, Any] = {}

    for param_name, param in sig.parameters.items():
        if param.annotation == inspect.Parameter.empty:
            continue

        annotation = param.annotation
        field_info = None

        # Check if it's Annotated[Type, Field(...)]
        if get_origin(annotation) is Annotated:
            args = get_args(annotation)
            annotation = args[0]  # The actual type
            # Look for FieldInfo in metadata
            for metadata in args[1:]:
                if isinstance(metadata, FieldInfo):
                    field_info = metadata
                    break

        default = _resolve_default(param, field_info)

        # Check if it's list[SomeModel]
        origin = get_origin(annotation)
        if origin is list:
            args = get_args(annotation)
            if args and inspect.isclass(args[0]):
                try:
                    if issubclass(args[0], BaseModel):
                        model_cls = args[0]
                        # Add field with JSON parser
                        fields[param_name] = (annotation, default)
                        validators[f"_parse_{param_name}"] = field_validator(
                            param_name, mode="before"
                        )(json_list_parser(model_cls))
                    else:
                        fields[param_name] = (annotation, default)
                except TypeError:
                    # Not a valid class for issubclass
                    fields[param_name] = (annotation, default)
            else:
                fields[param_name] = (annotation, default)
        else:
            fields[param_name] = (annotation, default)

    # Create base model with ConfigDict
    class _BaseModel(BaseModel):
        model_config = ConfigDict(arbitrary_types_allowed=True)

    # Create args_schema with validators
    args_schema = create_model(
        f"{func.__name__}Args",
        __base__=_BaseModel,
        __validators__=validators,
        **fields,
    )

    return tool(args_schema=args_schema)(func)
