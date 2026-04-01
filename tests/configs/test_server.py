"""Tests for server configuration."""

from pathlib import Path

import pytest

from langrepl.configs.server import ServerConfig, ServerProtocol


class TestServerConfig:
    """Tests for ServerConfig model."""

    def test_defaults(self):
        config = ServerConfig()
        assert config.protocol == ServerProtocol.AGUI
        assert config.backend_url == "http://0.0.0.0:8000"
        assert config.frontend_url == "http://localhost:3000"
        assert config.host == "0.0.0.0"
        assert config.port == 8000
        assert config.ui_port == 3000

    def test_custom_values(self):
        config = ServerConfig(
            protocol=ServerProtocol.LANGSMITH,
            backend_url="http://127.0.0.1:9000",
            frontend_url="http://localhost:3001",
        )
        assert config.protocol == ServerProtocol.LANGSMITH
        assert config.host == "127.0.0.1"
        assert config.port == 9000
        assert config.ui_port == 3001

    def test_protocol_enum(self):
        assert ServerProtocol.AG.value == "ag"
        assert ServerProtocol.AGUI.value == "agui"
        assert ServerProtocol.LANGSMITH.value == "langsmith"

    @pytest.mark.asyncio
    async def test_from_yaml_missing_file_raises(self, temp_dir: Path):
        with pytest.raises(FileNotFoundError):
            await ServerConfig.from_yaml(temp_dir / "nonexistent.yml")

    @pytest.mark.asyncio
    async def test_from_yaml_valid_file(self, temp_dir: Path):
        yml = temp_dir / "config.server.yml"
        yml.write_text(
            "version: 1.0.0\nprotocol: ag\nbackend_url: http://0.0.0.0:9000\n"
        )
        config = await ServerConfig.from_yaml(yml)
        assert config.protocol == ServerProtocol.AG
        assert config.port == 9000
