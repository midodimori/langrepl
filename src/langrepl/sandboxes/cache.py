"""Profile caching for sandbox backends."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


class ProfileCache:
    """Cache for generated sandbox profiles."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir

    def _compute_hash(
        self, config_name: str, working_dir: Path, config_dict: dict
    ) -> str:
        """Compute cache key hash."""
        data = json.dumps(
            {
                "name": config_name,
                "working_dir": str(working_dir),
                "config": config_dict,
            },
            sort_keys=True,
        )
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def get_path(
        self,
        config_name: str,
        working_dir: Path,
        config_dict: dict,
        suffix: str = ".sb",
    ) -> Path:
        """Get cache file path for given config."""
        hash_key = self._compute_hash(config_name, working_dir, config_dict)
        return self.cache_dir / f"{config_name}_{hash_key}{suffix}"
