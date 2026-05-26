from typing import Any, cast

from langrepl.checkpointer import serde


def test_create_checkpoint_serializer_passes_msgpack_allowlist_when_supported(
    monkeypatch,
):
    class SerializerWithMsgpackAllowlist:
        def __init__(self, *, allowed_json_modules, allowed_msgpack_modules):
            self.allowed_json_modules = allowed_json_modules
            self.allowed_msgpack_modules = allowed_msgpack_modules

    monkeypatch.setattr(serde, "JsonPlusSerializer", SerializerWithMsgpackAllowlist)

    serializer = cast(Any, serde.create_checkpoint_serializer())

    assert serializer.allowed_json_modules == serde.LANGREPL_ALLOWED_JSON_MODULES
    assert serializer.allowed_msgpack_modules == serde.LANGREPL_ALLOWED_MSGPACK_TYPES


def test_create_checkpoint_serializer_supports_legacy_constructor(monkeypatch):
    class LegacySerializer:
        def __init__(self, *, allowed_json_modules):
            self.allowed_json_modules = allowed_json_modules

    monkeypatch.setattr(serde, "JsonPlusSerializer", LegacySerializer)

    serializer = cast(Any, serde.create_checkpoint_serializer())

    assert serializer.allowed_json_modules == serde.LANGREPL_ALLOWED_JSON_MODULES
