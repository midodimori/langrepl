"""Tests for checkpointer serde."""

from langrepl.checkpointer.base import SERDE
from langrepl.middlewares.approval import InterruptPayload


class TestSerdeRoundtrip:
    def test_interrupt_payload_roundtrip_via_msgpack(self):
        """SERDE should serialize and deserialize InterruptPayload without data loss."""
        payload = InterruptPayload(
            question="Allow running bash?",
            options=["allow", "always allow", "deny", "always deny"],
        )

        typ, data = SERDE.dumps_typed(payload)

        assert typ == "msgpack"
        result = SERDE.loads_typed((typ, data))

        assert isinstance(result, InterruptPayload)
        assert result.question == payload.question
        assert result.options == payload.options
