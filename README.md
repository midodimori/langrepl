# Langrepl

Interactive terminal CLI for building and running LLM agents. Built with LangChain, LangGraph, Prompt Toolkit, and Rich.

[![CI](https://github.com/midodimori/langrepl/actions/workflows/ci.yml/badge.svg)](https://github.com/midodimori/langrepl/actions/workflows/ci.yml)
[![PyPI - Version](https://img.shields.io/pypi/v/langrepl?logo=pypi&logoColor=white)](https://pypi.org/project/langrepl/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/langrepl?logo=pypi&logoColor=white)](https://pypi.org/project/langrepl/)
[![Python Version](https://img.shields.io/pypi/pyversions/langrepl?logo=python&logoColor=white)](https://pypi.org/project/langrepl/)
[![License](https://img.shields.io/github/license/midodimori/langrepl)](https://github.com/midodimori/langrepl/blob/main/LICENSE)

https://github.com/user-attachments/assets/d95444c9-733f-481d-80c7-7d1cc28a732a

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
  - [From PyPI](#from-pypi)
  - [From GitHub](#from-github)
  - [From Source](#from-source)
  - [Configure API Keys](#configure-api-keys)
  - [Tracing](#tracing)
- [Quick Start](#quick-start)
  - [Interactive Chat Mode](#interactive-chat-mode)
  - [LangGraph Server Mode](#langgraph-server-mode)
- [Interactive Commands](#interactive-commands)
  - [Conversation Management](#conversation-management)
  - [Configuration](#configuration)
  - [Utilities](#utilities)
- [Usage](#usage)
  - [Agents](#agents)
  - [LLMs](#llms)
  - [Checkpointers](#checkpointers)
  - [Sub-Agents](#sub-agents)
  - [Custom Tools](#custom-tools)
  - [MCP Servers](#mcp-servers-configmcpjson)
  - [Tool Approval](#tool-approval-configapprovaljson)
- [Development](#development)
- [License](#license)

## Features

- **[Deep Agent Architecture](https://blog.langchain.com/deep-agents/)** - Planning tools, virtual filesystem, and
  sub-agent delegation for complex multi-step tasks
- **LangGraph Server Mode** - Run agents as API servers with LangGraph Studio integration for visual debugging
- **Multi-Provider LLM Support** - OpenAI, Anthropic, Google, AWS Bedrock, Ollama, DeepSeek, ZhipuAI, and local models (LMStudio, Ollama)
- **Multimodal Image Support** - Send images to vision models via clipboard paste, drag-and-drop, or absolute paths
- **Extensible Tool System** - File operations, web search, terminal access, grep search, and MCP server integration
- **Persistent Conversations** - SQLite-backed thread storage with resume, replay, and compression
- **User Memory** - Project-specific custom instructions and preferences that persist across conversations
- **Human-in-the-Loop** - Configurable tool approval system with regex-based allow/deny rules
- **Cost Tracking (Beta)** - Token usage and cost calculation per conversation
- **MCP Server Support** - Integrate external tool servers via the MCP protocol

## Prerequisites

- **Python 3.13+** - Required for the project
- **[uv](https://docs.astral.sh/uv/getting-started/installation/)** - Fast Python package
  installer ([install instructions](https://docs.astral.sh/uv/getting-started/installation/))
- **[ripgrep (rg)](https://github.com/BurntSushi/ripgrep)** - Required for fast code search (`grep_search` tool) and directory structure visualization (`get_directory_structure` tool):
  - macOS: `brew install ripgrep`
  - Ubuntu/Debian: `sudo apt install ripgrep`
  - Arch Linux: `sudo pacman -S ripgrep`
  - Windows: `choco install ripgrep` or download from [releases](https://github.com/BurntSushi/ripgrep/releases)
- **[fd](https://github.com/sharkdp/fd)** - Required for fast file/directory completion with `@` (fallback when not in a Git repository):
  - macOS: `brew install fd`
  - Ubuntu/Debian: `sudo apt install fd-find`
  - Arch Linux: `sudo pacman -S fd`
  - Windows: `choco install fd` or download from [releases](https://github.com/sharkdp/fd/releases)
- **Node.js & npm** (optional) - Required only if using MCP servers that run via npx

## Installation

The `.langrepl` config directory is created in your **working directory** (or use `-w` to specify a location).
Aliases: `langrepl` or `lg`

### From PyPI

**Quick try (no installation):**
```bash
uvx langrepl
uvx langrepl -w /path  # specify working dir
```

**Install globally:**
```bash
uv tool install langrepl
# or with pipx:
pipx install langrepl
```

Then run from any directory:
```bash
langrepl              # or: lg
langrepl -w /path     # specify working directory
```

### From GitHub

**Quick try (no installation):**
```bash
uvx --from git+https://github.com/midodimori/langrepl langrepl
uvx --from git+https://github.com/midodimori/langrepl langrepl -w /path  # specify working dir
```

**Install globally:**
```bash
uv tool install git+https://github.com/midodimori/langrepl
```

Then run from any directory:
```bash
langrepl              # or: lg
langrepl -w /path     # specify working directory
```

### From Source

Clone and install:
```bash
git clone https://github.com/midodimori/langrepl.git
cd langrepl
make install
uv tool install --editable .
```

Then run from any directory (same as above).

### Configure API Keys

Set API keys via `.env`:

```bash
LLM__OPENAI_API_KEY=your_openai_api_key_here
LLM__ANTHROPIC_API_KEY=your_anthropic_api_key_here
LLM__GOOGLE_API_KEY=your_google_api_key_here
LLM__DEEPSEEK_API_KEY=your_deepseek_api_key_here
LLM__ZHIPUAI_API_KEY=your_zhipuai_api_key_here
```

### Tracing

#### LangSmith

Add to `.env`:

```bash
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT="https://api.smith.langchain.com"
LANGCHAIN_API_KEY="your_langsmith_api_key"
LANGCHAIN_PROJECT="your_project_name"
```

## Quick Start

Langrepl ships with multiple prebuilt agents:
- **`general`** (default) - General-purpose agent for research, writing, analysis, and planning
- **`claude-style-coder`** - Software development agent mimicking Claude Code's behavior
- **`code-reviewer`** - Code review agent focusing on quality and best practices

### Interactive Chat Mode

```bash
langrepl              # Start interactive session (general agent by default)
langrepl -a general   # Use specific agent
langrepl -r           # Resume last conversation
langrepl -am ACTIVE   # Set approval mode (SEMI_ACTIVE, ACTIVE, AGGRESSIVE)
langrepl -w /path     # Set working directory
lg                    # Quick alias
```

### One-Shot Mode

```bash
langrepl "your message here"                    # Send message and exit
langrepl "what is 2+2?" -am aggressive          # With approval mode
langrepl -a general "search for latest news"    # Use specific agent
langrepl -r "continue from where we left off"   # Resume conversation
```

### LangGraph Server Mode

```bash
langrepl -s -a general                # Start LangGraph server
langrepl -s -a general -am ACTIVE     # With approval mode

# Server: http://localhost:2024
# Studio: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
# API Docs: http://localhost:2024/docs
```

Server features:
- Auto-generates `langgraph.json` configuration
- Creates/updates assistants via LangGraph API
- Enables visual debugging with LangGraph Studio
- Supports all agent configs and MCP servers

## Interactive Commands

### Conversation Management

<details>
<summary><code>/resume</code> - Switch between conversation threads</summary>

Shows list of all saved threads with timestamps. Select one to continue that conversation.

</details>

<details>
<summary><code>/replay</code> - Branch from previous message</summary>

Shows all previous human messages in current thread. Select one to branch from that point while preserving the original
conversation.

</details>

<details>
<summary><code>/compress</code> - Compress conversation history</summary>

Compresses messages using LLM summarization to reduce token usage. Creates new thread with compressed history (e.g., 150
messages/45K tokens → 3 messages/8K tokens).

</details>

<details>
<summary><code>/clear</code> - Start new conversation</summary>

Clear screen and start a new conversation thread while keeping previous thread saved.

</details>

### Configuration

<details>
<summary><code>/agents</code> - Switch agent</summary>

Shows all configured agents with interactive selector. Switch between specialized agents (e.g., coder, researcher,
analyst).

</details>

<details>
<summary><code>/model</code> - Switch LLM model</summary>

Shows all configured models with interactive selector. Switch between models for cost/quality tradeoffs.

</details>

<details>
<summary><code>/tools</code> - View available tools</summary>

Lists all tools from impl/, internal/, and MCP servers.

</details>

<details>
<summary><code>/mcp</code> - Manage MCP servers</summary>

View and toggle enabled/disabled MCP servers interactively.

</details>

<details>
<summary><code>/memory</code> - Edit user memory</summary>

Opens `.langrepl/memory.md` for custom instructions and preferences. Content is automatically injected into agent
prompts.

**Advanced:** Use `{user_memory}` placeholder in custom agent prompts to control placement. If omitted, memory
auto-appends to end.

</details>

### Utilities

<details>
<summary><code>/graph [--browser]</code> - Visualize agent graph</summary>

Renders in terminal (ASCII) or opens in browser with `--browser` flag.

</details>

<details>
<summary><code>/help</code> - Show help</summary>

</details>

<details>
<summary><code>/exit</code> - Exit application</summary>

</details>

## Usage

Configs are auto-generated in `.langrepl/` on first run.

### Agents

`.langrepl/agents/*.yml`:
```yaml
# agents/my-agent.yml (filename must match agent name)
name: my-agent
prompt: prompts/my_agent.md  # Single file or array of files
llm: haiku-4.5               # References llms/*.yml
checkpointer: sqlite         # References checkpointers/*.yml
recursion_limit: 40
tool_output_max_tokens: 10000
default: true
tools:
  - impl:file_system:read_file
  - mcp:context7:resolve-library-id
subagents:
  - general-purpose         # References subagents/*.yml
compression:
  auto_compress_enabled: true
  auto_compress_threshold: 0.8
  compression_llm: haiku-4.5
```

<details>
<summary>Single-file format: .langrepl/config.agents.yml</summary>

```yaml
agents:
  - name: my-agent
    prompt: prompts/my_agent.md
    llm: haiku-4.5
    checkpointer: sqlite
    recursion_limit: 40
    tool_output_max_tokens: 10000
    default: true
    tools:
      - impl:file_system:read_file
      - mcp:context7:resolve-library-id
    subagents:
      - general-purpose
    compression:
      auto_compress_enabled: true
      auto_compress_threshold: 0.8
      compression_llm: haiku-4.5
```

</details>

**Tool naming**: `<category>:<module>:<function>` with wildcard support (`*`, `?`, `[seq]`)
- `impl:*:*` - All built-in tools
- `impl:file_system:read_*` - All read_* tools in file_system
- `mcp:server:*` - All tools from MCP server

### LLMs

`.langrepl/llms/*.yml`:
```yaml
# llms/anthropic.yml (organize by provider, filename is flexible)
- model: claude-haiku-4-5
  alias: haiku-4.5
  provider: anthropic
  max_tokens: 10000
  temperature: 0.1
  context_window: 200000
  input_cost_per_mtok: 1.00
  output_cost_per_mtok: 5.00
```

<details>
<summary>Single-file format: .langrepl/config.llms.yml</summary>

```yaml
llms:
  - model: claude-haiku-4-5
    alias: haiku-4.5
    provider: anthropic
    max_tokens: 10000
    temperature: 0.1
    context_window: 200000
    input_cost_per_mtok: 1.00
    output_cost_per_mtok: 5.00
```

</details>

### Checkpointers

`.langrepl/checkpointers/*.yml`:
```yaml
# checkpointers/sqlite.yml (filename must match checkpointer type)
type: sqlite
max_connections: 10
```

```yaml
# checkpointers/memory.yml (filename must match checkpointer type)
type: memory
max_connections: 1
```

<details>
<summary>Single-file format: .langrepl/config.checkpointers.yml</summary>

```yaml
checkpointers:
  - type: sqlite
    max_connections: 10
  - type: memory
    max_connections: 1
```

</details>

**Checkpointer types**:
- `sqlite` - Persistent SQLite-backed storage (default, stored in `.langrepl/.db/checkpoints.db`)
- `memory` - In-memory storage (ephemeral, lost on exit)

### Sub-Agents

Sub-agents use the same config structure as main agents.

`.langrepl/subagents/*.yml`:
```yaml
# subagents/code-reviewer.yml (filename must match subagent name)
name: code-reviewer
prompt: prompts/code-reviewer.md
llm: haiku-4.5
tools: [impl:file_system:read_file]
```

<details>
<summary>Single-file format: .langrepl/config.subagents.yml</summary>

```yaml
agents:
  - name: code-reviewer
    prompt: prompts/code-reviewer.md
    llm: haiku-4.5
    tools: [impl:file_system:read_file]
```

</details>

**Add custom**: Create prompt, add config file, reference in parent agent's `subagents` list.

### Custom Tools

1. Implement in `src/tools/impl/my_tool.py`:
   ```python
   from langchain.tools import tool

   @tool()
   def my_tool(query: str) -> str:
       """Tool description."""
       return result
   ```

2. Register in `src/tools/factory.py`:
   ```python
   MY_TOOLS = [my_tool]
   self.impl_tools.extend(MY_TOOLS)
   ```

3. Reference: `impl:my_tool:my_tool`

### MCP Servers (`config.mcp.json`)

```json
{
  "mcpServers": {
    "my-server": {
      "command": "uvx",
      "args": ["my-mcp-package"],
      "transport": "stdio",
      "enabled": true,
      "include": ["tool1"],
      "exclude": [],
      "repair_command": "rm -rf .some_cache"
    }
  }
}
```

- `repair_command`: Runs if server fails, then run this command before retrying
- Suppress stderr: `"command": "sh", "args": ["-c", "npx pkg 2>/dev/null"]`
- Reference: `mcp:my-server:tool1`
- Examples: [useful-mcp-servers.json](examples/useful-mcp-servers.json)

### Tool Approval (`config.approval.json`)

```json
{
  "always_allow": [
    {
      "name": "read_file",
      "args": null
    },
    {
      "name": "run_command",
      "args": "pwd"
    }
  ],
  "always_deny": [
    {
      "name": "run_command",
      "args": "rm -rf /.*"
    }
  ]
}
```

**Modes**: `SEMI_ACTIVE` (ask unless whitelisted), `ACTIVE` (auto-approve except denied), `AGGRESSIVE` (bypass all)

## Development

For local development without global install:

```bash
git clone https://github.com/midodimori/langrepl.git
cd langrepl
make install
```

**Run from within repository:**
```bash
uv run langrepl              # Start interactive session
uv run langrepl -w /path     # Specify working directory
uv run langrepl -s -a general  # Start LangGraph server
```

**Development commands:**
```bash
make install      # Install dependencies + pre-commit hooks
make lint-fix     # Format and lint code
make test         # Run tests
make pre-commit   # Run pre-commit on all files
make clean        # Remove cache/build artifacts
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
