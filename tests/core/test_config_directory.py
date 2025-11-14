import pytest

from src.core.config import BatchAgentConfig, BatchCheckpointerConfig, BatchLLMConfig


@pytest.mark.asyncio
async def test_llm_config_old_format(temp_dir):
    config_file = temp_dir / "config.llms.yml"
    config_file.write_text(
        """
llms:
  - model: test-model
    alias: test-llm
    provider: anthropic
    max_tokens: 1000
    temperature: 0.1
"""
    )

    config = await BatchLLMConfig.from_yaml(file_path=config_file)
    assert len(config.llms) == 1
    assert config.llms[0].alias == "test-llm"


@pytest.mark.asyncio
async def test_llm_config_new_format(temp_dir):
    llms_dir = temp_dir / "llms"
    llms_dir.mkdir()

    # Files can be organized by provider
    (llms_dir / "anthropic.yml").write_text(
        """
- model: test-model
  alias: test-llm
  provider: anthropic
  max_tokens: 1000
  temperature: 0.1
"""
    )

    config = await BatchLLMConfig.from_yaml(dir_path=llms_dir)
    assert len(config.llms) == 1
    assert config.llms[0].alias == "test-llm"


@pytest.mark.asyncio
async def test_llm_config_combine_both_formats(temp_dir):
    """Test that unique LLMs from both file and directory can be loaded together."""
    config_file = temp_dir / "config.llms.yml"
    config_file.write_text(
        """
llms:
  - model: old-model
    alias: old-llm
    provider: anthropic
    max_tokens: 1000
    temperature: 0.1
  - model: file-model
    alias: file-llm
    provider: openai
    max_tokens: 2000
    temperature: 0.2
"""
    )

    llms_dir = temp_dir / "llms"
    llms_dir.mkdir()
    (llms_dir / "anthropic.yml").write_text(
        """
- model: new-model
  alias: new-llm
  provider: anthropic
  max_tokens: 1000
  temperature: 0.1
- model: dir-model
  alias: dir-llm
  provider: anthropic
  max_tokens: 3000
  temperature: 0.3
"""
    )

    config = await BatchLLMConfig.from_yaml(file_path=config_file, dir_path=llms_dir)
    assert len(config.llms) == 4

    llm_dict = {llm.alias: llm for llm in config.llms}
    assert "old-llm" in llm_dict
    assert "file-llm" in llm_dict
    assert "new-llm" in llm_dict
    assert "dir-llm" in llm_dict


@pytest.mark.asyncio
async def test_llm_config_duplicate_between_formats_raises_error(temp_dir):
    """Test that duplicate LLMs between file and directory raise an error."""
    config_file = temp_dir / "config.llms.yml"
    config_file.write_text(
        """
llms:
  - model: old-model
    alias: duplicate-llm
    provider: anthropic
    max_tokens: 1000
    temperature: 0.1
"""
    )

    llms_dir = temp_dir / "llms"
    llms_dir.mkdir()
    (llms_dir / "openai.yml").write_text(
        """
- model: new-model
  alias: duplicate-llm
  provider: openai
  max_tokens: 2000
  temperature: 0.2
"""
    )

    with pytest.raises(ValueError, match=r"Duplicate llm 'alias': 'duplicate-llm'"):
        await BatchLLMConfig.from_yaml(file_path=config_file, dir_path=llms_dir)


@pytest.mark.asyncio
async def test_checkpointer_config_old_format(temp_dir):
    config_file = temp_dir / "config.checkpointers.yml"
    config_file.write_text(
        """
checkpointers:
  - type: sqlite
    max_connections: 10
"""
    )

    config = await BatchCheckpointerConfig.from_yaml(file_path=config_file)
    assert len(config.checkpointers) == 1
    assert config.checkpointers[0].type == "sqlite"


@pytest.mark.asyncio
async def test_checkpointer_config_new_format(temp_dir):
    checkpointers_dir = temp_dir / "checkpointers"
    checkpointers_dir.mkdir()

    (checkpointers_dir / "sqlite.yml").write_text(
        """
type: sqlite
max_connections: 10
"""
    )

    config = await BatchCheckpointerConfig.from_yaml(dir_path=checkpointers_dir)
    assert len(config.checkpointers) == 1
    assert config.checkpointers[0].type == "sqlite"


@pytest.mark.asyncio
async def test_agent_config_old_format(temp_dir, mock_llm_config):
    config_file = temp_dir / "config.agents.yml"
    config_file.write_text(
        f"""
agents:
  - name: test-agent
    prompt: "test prompt"
    llm: {mock_llm_config.alias}
    default: true
"""
    )

    llm_config = BatchLLMConfig(llms=[mock_llm_config])
    config = await BatchAgentConfig.from_yaml(
        file_path=config_file, batch_llm_config=llm_config
    )
    assert len(config.agents) == 1
    assert config.agents[0].name == "test-agent"


@pytest.mark.asyncio
async def test_agent_config_new_format(temp_dir, mock_llm_config):
    agents_dir = temp_dir / "agents"
    agents_dir.mkdir()

    (agents_dir / "test-agent.yml").write_text(
        f"""
name: test-agent
prompt: "test prompt"
llm: {mock_llm_config.alias}
default: true
"""
    )

    llm_config = BatchLLMConfig(llms=[mock_llm_config])
    config = await BatchAgentConfig.from_yaml(
        dir_path=agents_dir, batch_llm_config=llm_config
    )
    assert len(config.agents) == 1
    assert config.agents[0].name == "test-agent"


@pytest.mark.asyncio
async def test_agent_config_merge_both_formats(temp_dir, mock_llm_config):
    config_file = temp_dir / "config.agents.yml"
    config_file.write_text(
        f"""
agents:
  - name: old-agent
    prompt: "old prompt"
    llm: {mock_llm_config.alias}
    default: true
"""
    )

    agents_dir = temp_dir / "agents"
    agents_dir.mkdir()
    (agents_dir / "new-agent.yml").write_text(
        f"""
name: new-agent
prompt: "new prompt"
llm: {mock_llm_config.alias}
default: false
"""
    )

    llm_config = BatchLLMConfig(llms=[mock_llm_config])
    config = await BatchAgentConfig.from_yaml(
        file_path=config_file, dir_path=agents_dir, batch_llm_config=llm_config
    )
    assert len(config.agents) == 2
    agent_names = {agent.name for agent in config.agents}
    assert "old-agent" in agent_names
    assert "new-agent" in agent_names


@pytest.mark.asyncio
async def test_update_agent_llm_directory_format(temp_dir):
    agents_dir = temp_dir / "agents"
    agents_dir.mkdir()

    (agents_dir / "test-agent.yml").write_text(
        """
name: test-agent
prompt: "test prompt"
llm: old-llm
default: true
"""
    )

    await BatchAgentConfig.update_agent_llm(
        file_path=temp_dir / "config.agents.yml",
        agent_name="test-agent",
        new_llm_name="new-llm",
        dir_path=agents_dir,
    )

    updated_content = (agents_dir / "test-agent.yml").read_text()
    assert "llm: new-llm" in updated_content
    assert "llm: old-llm" not in updated_content


@pytest.mark.asyncio
async def test_update_agent_llm_fallback_to_file(temp_dir):
    config_file = temp_dir / "config.agents.yml"
    config_file.write_text(
        """
agents:
  - name: test-agent
    prompt: "test prompt"
    llm: old-llm
    default: true
"""
    )

    await BatchAgentConfig.update_agent_llm(
        file_path=config_file,
        agent_name="test-agent",
        new_llm_name="new-llm",
        dir_path=temp_dir / "agents",
    )

    updated_content = config_file.read_text()
    assert "llm: new-llm" in updated_content
    assert "llm: old-llm" not in updated_content


@pytest.mark.asyncio
async def test_update_default_agent_directory_format(temp_dir):
    agents_dir = temp_dir / "agents"
    agents_dir.mkdir()

    (agents_dir / "agent1.yml").write_text(
        """
name: agent1
prompt: "test prompt"
llm: test-llm
default: true
"""
    )

    (agents_dir / "agent2.yml").write_text(
        """
name: agent2
prompt: "test prompt"
llm: test-llm
default: false
"""
    )

    await BatchAgentConfig.update_default_agent(
        file_path=temp_dir / "config.agents.yml",
        agent_name="agent2",
        dir_path=agents_dir,
    )

    agent1_content = (agents_dir / "agent1.yml").read_text()
    agent2_content = (agents_dir / "agent2.yml").read_text()

    assert "default: false" in agent1_content or "default: False" in agent1_content
    assert "default: true" in agent2_content or "default: True" in agent2_content
