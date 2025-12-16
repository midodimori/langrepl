"""Checkpointer configuration classes."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

from langrepl.configs.base import VersionedConfig
from langrepl.configs.utils import (
    _load_dir_items,
    _load_single_file,
    _validate_no_duplicates,
)
from langrepl.core.constants import CHECKPOINTER_CONFIG_VERSION


class CheckpointerProvider(str, Enum):
    SQLITE = "sqlite"
    MEMORY = "memory"


class CheckpointerConfig(VersionedConfig):
    version: str = Field(
        default=CHECKPOINTER_CONFIG_VERSION, description="Config schema version"
    )
    type: CheckpointerProvider = Field(description="The checkpointer type")

    @classmethod
    def get_latest_version(cls) -> str:
        return CHECKPOINTER_CONFIG_VERSION


class BatchCheckpointerConfig(BaseModel):
    checkpointers: list[CheckpointerConfig] = Field(
        description="The checkpointer configurations"
    )

    @property
    def checkpointer_names(self) -> list[str]:
        return [cp.type for cp in self.checkpointers]

    def get_checkpointer_config(
        self, checkpointer_name: str
    ) -> CheckpointerConfig | None:
        return next(
            (cp for cp in self.checkpointers if cp.type == checkpointer_name), None
        )

    @classmethod
    async def from_yaml(
        cls,
        file_path: Path | None = None,
        dir_path: Path | None = None,
    ) -> BatchCheckpointerConfig:
        checkpointers = []

        if file_path and file_path.exists():
            checkpointers.extend(
                await _load_single_file(file_path, "checkpointers", CheckpointerConfig)
            )

        if dir_path:
            checkpointers.extend(
                await _load_dir_items(
                    dir_path,
                    key="type",
                    config_type="Checkpointer",
                    config_class=CheckpointerConfig,
                )
            )

        _validate_no_duplicates(checkpointers, key="type", config_type="Checkpointer")
        return cls.model_validate({"checkpointers": checkpointers})
