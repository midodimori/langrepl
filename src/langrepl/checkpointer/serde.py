"""Checkpoint serialization configuration for Langrepl types."""

from __future__ import annotations

import inspect

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from langrepl.middlewares.approval import InterruptPayload

LANGREPL_ALLOWED_MSGPACK_TYPES: tuple[type, ...] = (InterruptPayload,)
LANGREPL_ALLOWED_JSON_MODULES: tuple[tuple[str, ...], ...] = tuple(
    (*allowed_type.__module__.split("."), allowed_type.__name__)
    for allowed_type in LANGREPL_ALLOWED_MSGPACK_TYPES
)


def create_checkpoint_serializer() -> JsonPlusSerializer:
    """Create a strict-compatible checkpoint serializer for Langrepl payloads."""
    if "allowed_msgpack_modules" in inspect.signature(JsonPlusSerializer).parameters:
        return JsonPlusSerializer(
            allowed_json_modules=LANGREPL_ALLOWED_JSON_MODULES,
            allowed_msgpack_modules=LANGREPL_ALLOWED_MSGPACK_TYPES,
        )

    return JsonPlusSerializer(allowed_json_modules=LANGREPL_ALLOWED_JSON_MODULES)
