"""Checkpoint serialization configuration for Langrepl types."""

from __future__ import annotations

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from langrepl.middlewares.approval import InterruptPayload

LANGREPL_ALLOWED_MSGPACK_TYPES = (InterruptPayload,)


def create_checkpoint_serializer() -> JsonPlusSerializer:
    """Create a strict-compatible checkpoint serializer for Langrepl payloads."""
    return JsonPlusSerializer(
        allowed_msgpack_modules=LANGREPL_ALLOWED_MSGPACK_TYPES,
    )
