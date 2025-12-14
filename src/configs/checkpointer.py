"""Checkpointer configuration models."""

from pathlib import Path

from pydantic import BaseModel, Field

from src.configs.base import (
    VersionedConfig,
    _load_dir_items,
    _load_single_file,
    _validate_no_duplicates,
)
from src.configs.enums import CheckpointerProvider
from src.core.constants import (
    CHECKPOINTER_CONFIG_VERSION,
    CONFIG_CHECKPOINTERS_DIR,
    CONFIG_CHECKPOINTERS_FILE_NAME,
)

__all__ = [
    "BatchCheckpointerConfig",
    "CheckpointerConfig",
]


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
        working_dir: Path,
    ) -> "BatchCheckpointerConfig":
        checkpointers = []
        file_path = working_dir / CONFIG_CHECKPOINTERS_FILE_NAME
        dir_path = working_dir / CONFIG_CHECKPOINTERS_DIR

        if file_path.exists():
            checkpointers.extend(
                await _load_single_file(
                    file_path, "checkpointers", CheckpointerConfig, working_dir
                )
            )

        if dir_path.exists():
            checkpointers.extend(
                await _load_dir_items(
                    dir_path,
                    key="type",
                    config_type="Checkpointer",
                    config_class=CheckpointerConfig,
                    working_dir=working_dir,
                )
            )

        _validate_no_duplicates(checkpointers, key="type", config_type="Checkpointer")
        return cls.model_validate({"checkpointers": checkpointers})
