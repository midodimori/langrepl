import pytest

from langrepl.checkpointer.factory import CheckpointerFactory
from langrepl.configs import CheckpointerConfig, CheckpointerProvider
from langrepl.middlewares.approval import InterruptPayload


def assert_interrupt_payload_round_trips(checkpointer):
    payload = InterruptPayload(
        question="Allow running tool?", options=["allow", "deny"]
    )

    serialized = checkpointer.serde.dumps_typed(payload)
    restored = checkpointer.serde.loads_typed(serialized)

    assert restored == payload


class TestCheckpointerFactory:
    @pytest.mark.asyncio
    async def test_create_memory_checkpointer(self):
        factory = CheckpointerFactory()
        config = CheckpointerConfig(type=CheckpointerProvider.MEMORY)

        async with factory.create(config, ":memory:") as checkpointer:
            assert checkpointer is not None
            assert checkpointer.__class__.__name__ == "MemoryCheckpointer"
            assert_interrupt_payload_round_trips(checkpointer)

    @pytest.mark.asyncio
    async def test_create_sqlite_checkpointer(self):
        factory = CheckpointerFactory()
        config = CheckpointerConfig(type=CheckpointerProvider.SQLITE)

        async with factory.create(config, ":memory:") as checkpointer:
            assert checkpointer is not None
            assert checkpointer.__class__.__name__ == "IndexedAsyncSqliteSaver"
            assert_interrupt_payload_round_trips(checkpointer)
