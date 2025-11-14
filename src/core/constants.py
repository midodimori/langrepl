from pathlib import Path

UNKNOWN = "unknown"
DEFAULT_THEME = "tokyo-night"
APP_NAME = "langrepl"
CONFIG_DIR_NAME = f".{APP_NAME}"
CONFIG_MCP_FILE_NAME = Path(f"{CONFIG_DIR_NAME}/config.mcp.json")
CONFIG_APPROVAL_FILE_NAME = Path(f"{CONFIG_DIR_NAME}/config.approval.json")
CONFIG_LANGGRAPH_FILE_NAME = Path(f"{CONFIG_DIR_NAME}/langgraph.json")
CONFIG_LLMS_FILE_NAME = Path(f"{CONFIG_DIR_NAME}/config.llms.yml")
CONFIG_CHECKPOINTERS_FILE_NAME = Path(f"{CONFIG_DIR_NAME}/config.checkpointers.yml")
CONFIG_AGENTS_FILE_NAME = Path(f"{CONFIG_DIR_NAME}/config.agents.yml")
CONFIG_SUBAGENTS_FILE_NAME = Path(f"{CONFIG_DIR_NAME}/config.subagents.yml")
CONFIG_CHECKPOINTS_URL_FILE_NAME = Path(f"{CONFIG_DIR_NAME}/config.checkpoints.db")
CONFIG_HISTORY_FILE_NAME = Path(f"{CONFIG_DIR_NAME}/.history")
CONFIG_MEMORY_FILE_NAME = Path(f"{CONFIG_DIR_NAME}/memory.md")

CONFIG_LLMS_DIR = Path(f"{CONFIG_DIR_NAME}/llms")
CONFIG_CHECKPOINTERS_DIR = Path(f"{CONFIG_DIR_NAME}/checkpointers")
CONFIG_AGENTS_DIR = Path(f"{CONFIG_DIR_NAME}/agents")
CONFIG_SUBAGENTS_DIR = Path(f"{CONFIG_DIR_NAME}/subagents")

DEFAULT_CONFIG_DIR_NAME = "resources/configs/default"

MAX_CONCURRENT_SUBAGENTS = 3
MAX_SUBAGENT_ITERATIONS = 25
