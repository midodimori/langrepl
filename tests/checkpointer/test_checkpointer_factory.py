import pytest

from src.checkpointer.factory import CheckpointerFactory
from src.core.config import CheckpointerConfig, CheckpointerProvider


class TestCheckpointerFactory:
    @pytest.mark.asyncio
    async def test_create_memory_checkpointer(self):
        factory = CheckpointerFactory()
        config = CheckpointerConfig(type=CheckpointerProvider.MEMORY)

        async with factory.create(config, ":memory:") as checkpointer:
            assert checkpointer is not None
            assert checkpointer.__class__.__name__ == "MemoryCheckpointer"

    @pytest.mark.asyncio
    async def test_create_sqlite_checkpointer(self):
        factory = CheckpointerFactory()
        config = CheckpointerConfig(type=CheckpointerProvider.SQLITE)

        async with factory.create(config, "file::memory:?cache=shared") as checkpointer:
            assert checkpointer is not None
            assert "Sqlite" in checkpointer.__class__.__name__
