# Langrepl

Interactive terminal CLI for building and running LLM agents. Built with LangChain, LangGraph, Prompt Toolkit, and Rich.

[![CI](https://github.com/midodimori/langrepl/actions/workflows/ci.yml/badge.svg)](https://github.com/midodimori/langrepl/actions/workflows/ci.yml)
[![PyPI - Version](https://img.shields.io/pypi/v/langrepl?logo=pypi&logoColor=white)](https://pypi.org/project/langrepl/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/langrepl?logo=pypi&logoColor=white)](https://pypi.org/project/langrepl/)
[![Python Version](https://img.shields.io/pypi/pyversions/langrepl?logo=python&logoColor=white)](https://pypi.org/project/langrepl/)
[![License](https://img.shields.io/github/license/midodimori/langrepl)](https://github.com/midodimori/langrepl/blob/main/LICENSE)

https://github.com/user-attachments/assets/f9573310-29dc-4c67-aa1b-cc6b6ab051a2

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
  - [From PyPI](#from-pypi)
  - [From GitHub](#from-github)
  - [From Source](#from-source)
  - [Environment Variables](#environment-variables)
  - [CLI Flags](#cli-flags)
- [Quick Start](#quick-start)
  - [Interactive Chat Mode](#interactive-chat-mode)
  - [One-Shot Mode](#one-shot-mode)
  - [LangGraph Server Mode](#langgraph-server-mode)
- [Interactive Commands](#interactive-commands)
  - [Conversation Management](#conversation-management)
  - [Configuration](#configuration)
  - [Utilities](#utilities)
- [Usage](#usage)
  - [Agents](#agents)
  - [Custom Prompts](#custom-prompts)
  - [LLMs](#llms)
  - [Checkpointers](#checkpointers)
  - [Sub-Agents](#sub-agents)
  - [Custom Tools](#custom-tools)
  - [Skills](#skills)
  - [MCP Servers](#mcp-servers-configmcpjson)
  - [Tool Approval](#tool-approval-configapprovaljson)
  - [Sandboxes (Beta)](#sandboxes-beta)
- [Development](#development)
- [License](#license)

## Features

- **[Deep Agent Architecture](https://blog.langchain.com/deep-agents/)** - Planning tools, virtual filesystem, and
  sub-agent delegation for complex multi-step tasks
- **LangGraph Server Mode** - Run agents as API servers with LangGraph Studio integration for visual debugging
- **Multi-Provider LLM Support** - OpenAI, Anthropic, Google, AWS Bedrock, Ollama, DeepSeek, ZhipuAI, and local models (LMStudio, Ollama)
- **Multimodal Image Support** - Send images to vision models via clipboard paste, drag-and-drop, or absolute paths
- **Extensible Tool System** - File operations, web search, terminal access, grep search, and MCP server integration
- **[Skill System](https://github.com/anthropics/skills)** - Modular knowledge packages that extend agent capabilities with specialized workflows and domain expertise
- **Persistent Conversations** - SQLite-backed thread storage with resume, replay, and compression
- **User Memory** - Project-specific custom instructions and preferences that persist across conversations
- **Human-in-the-Loop** - Configurable tool approval system with regex-based allow/deny rules
- **Cost Tracking (Beta)** - Token usage and cost calculation per conversation
- **MCP Server Support** - Integrate external tool servers via MCP protocol with optional stateful connections
- **Sandbox (Beta)** - Secure isolated execution for tools with filesystem, network, and syscall restrictions

## Prerequisites

- **Python 3.13+** - Required for the project
- **[uv](https://docs.astral.sh/uv/getting-started/installation/)** - Fast Python package
  installer ([install instructions](https://docs.astral.sh/uv/getting-started/installation/))
- **[ripgrep (rg)](https://github.com/BurntSushi/ripgrep)** - Required for fast code search (`grep_search` tool) and directory structure visualization (`get_directory_structure` tool):
  - macOS: `brew install ripgrep`
  - Ubuntu/Debian: `sudo apt install ripgrep`
  - Arch Linux: `sudo pacman -S ripgrep`
- **[fd](https://github.com/sharkdp/fd)** - Required for fast file/directory completion with `@` (fallback when not in a Git repository):
  - macOS: `brew install fd`
  - Ubuntu/Debian: `sudo apt install fd-find && sudo ln -s $(which fdfind) /usr/bin/fd`
  - Arch Linux: `sudo pacman -S fd`
- **tree** - Required for file system visualization:
  - macOS: `brew install tree`
  - Ubuntu/Debian: `sudo apt install tree`
  - Arch Linux: `sudo pacman -S tree`
- **bubblewrap** (Linux only, optional) - Required for sandbox feature:
  - Ubuntu/Debian: `sudo apt install bubblewrap`
  - Arch Linux: `sudo pacman -S bubblewrap`
  - Optional enhanced syscall filtering: `uv pip install pyseccomp`
- **Node.js & npm** (optional) - Required only if using MCP servers that run via npx

## Installation

The `.langrepl` config directory is created in your **working directory** (or use `-w` to specify a location).
Aliases: `langrepl` or `lg`

### From PyPI

**Quick try (no installation):**
```bash
uvx --python 3.13 langrepl
uvx --python 3.13 langrepl -w /path  # specify working dir
```

**Install globally:**
```bash
uv tool install --python 3.13 langrepl
# or with pipx:
pipx install --python 3.13 langrepl
```

Then run from any directory:
```bash
langrepl              # or: lg
langrepl -w /path     # specify working directory
```

### From GitHub

**Quick try (no installation):**
```bash
uvx --python 3.13 --from git+https://github.com/midodimori/langrepl langrepl
uvx --python 3.13 --from git+https://github.com/midodimori/langrepl langrepl -w /path  # specify working dir
```

**Install globally:**
```bash
uv tool install --python 3.13 git+https://github.com/midodimori/langrepl
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

### Environment Variables

Configure langrepl using environment variables via `.env` file or shell exports.

**Using `.env` file** (recommended):
```bash
# Create .env in your working directory
LLM__OPENAI_API_KEY=your_openai_api_key_here
LANGCHAIN_TRACING_V2=true
```

**Using shell exports**:
```bash
export LLM__OPENAI_API_KEY=your_openai_api_key_here
export LANGCHAIN_TRACING_V2=true
```

#### LLM Provider API Keys

```bash
# OpenAI
LLM__OPENAI_API_KEY=your_openai_api_key_here

# Anthropic
LLM__ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Google
LLM__GOOGLE_API_KEY=your_google_api_key_here

# DeepSeek
LLM__DEEPSEEK_API_KEY=your_deepseek_api_key_here

# Zhipu AI
LLM__ZHIPUAI_API_KEY=your_zhipuai_api_key_here

# AWS Bedrock (optional, falls back to AWS CLI credentials)
LLM__AWS_ACCESS_KEY_ID=your_aws_access_key_id
LLM__AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
LLM__AWS_SESSION_TOKEN=your_aws_session_token  # Optional

# Local model base URLs
LLM__OLLAMA_BASE_URL=http://localhost:11434      # Default
LLM__LMSTUDIO_BASE_URL=http://localhost:1234/v1  # Default
```

#### Tracing

**LangSmith** (recommended for debugging):
```bash
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key
LANGCHAIN_PROJECT=your_project_name              # Optional
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com  # Default
```

#### Proxy Settings

```bash
LLM__HTTP_PROXY=http://proxy.example.com:8080
LLM__HTTPS_PROXY=https://proxy.example.com:8443
```

#### Tool Settings

```bash
TOOL_SETTINGS__MAX_COLUMNS=1500      # Grep max columns (default: 1500)
TOOL_SETTINGS__CONTEXT_LINES=2       # Grep context lines (default: 2)
TOOL_SETTINGS__SEARCH_LIMIT=25       # Grep search limit (default: 25)
```

#### CLI Settings

```bash
CLI__THEME=tokyo-night               # UI theme (default: none (auto-detect), possible values: tokyo-day, tokyo-night)
CLI__PROMPT_STYLE="❯ "               # Prompt style (default: "❯ ")
CLI__ENABLE_WORD_WRAP=true           # Word wrap (default: true)
CLI__EDITOR=nano                     # Editor for /memory (default: nano)
CLI__MAX_AUTOCOMPLETE_SUGGESTIONS=10 # Autocomplete limit (default: 10)
```

#### Server Settings

```bash
SERVER__LANGGRAPH_SERVER_URL=http://localhost:2024  # Default
```

#### Other Settings

```bash
LOG_LEVEL=INFO                       # Log level (default: INFO)
SUPPRESS_GRPC_WARNINGS=true          # Suppress gRPC warnings (default: true)
```

### CLI Flags

```bash
langrepl [OPTIONS] [MESSAGE]
```

#### Positional Arguments

| Argument | Description |
|----------|-------------|
| `message` | Message to send in one-shot mode. Omit for interactive mode. |

#### Options

| Flag | Long Form | Description | Default |
|------|-----------|-------------|---------|
| `-h` | `--help` | Show help message and exit | - |
| `-w` | `--working-dir` | Working directory for the session | Current directory |
| `-a` | `--agent` | Agent to use for the session | Default agent from config |
| `-m` | `--model` | LLM model to use (overrides agent's default) | Agent's default model |
| `-r` | `--resume` | Resume the last conversation thread | false |
| `-t` | `--timer` | Enable performance timing for startup phases | false |
| `-s` | `--server` | Run in LangGraph server mode | false |
| `-am` | `--approval-mode` | Tool approval mode: `semi-active`, `active`, `aggressive` | From config |
| `-v` | `--verbose` | Enable verbose logging to console and `.langrepl/logs/app.log` | false |

#### Examples

```bash
# Interactive mode with default settings
langrepl

# One-shot mode
langrepl "What is the capital of France?"

# Specify working directory
langrepl -w /path/to/project

# Use specific agent
langrepl -a claude-style-coder

# Override agent's model
langrepl -a general -m gpt-4o

# Resume last conversation
langrepl -r

# Resume with new message
langrepl -r "Continue from where we left off"

# Set approval mode
langrepl -am aggressive

# LangGraph server mode
langrepl -s -a general

# Verbose logging
langrepl -v

# Combine flags
langrepl -w /my/project -a code-reviewer -am active -v
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

Lists all tools available to the current agent from impl/, internal/, and MCP servers.

</details>

<details>
<summary><code>/mcp</code> - Manage MCP servers</summary>

View and toggle enabled/disabled MCP servers interactively.

</details>

<details>
<summary><code>/memory</code> - Edit user memory</summary>

Opens `.langrepl/memory.md` for custom instructions and preferences. Content is automatically injected into agent
prompts.

</details>

<details>
<summary><code>/skills</code> - View available skills</summary>

Lists all skills available to the current agent with interactive selector. Skills are specialized knowledge packages that extend agent capabilities.

</details>

<details>
<summary><code>/approve</code> - Manage tool approval rules</summary>

Interactive tabbed interface for managing tool approval rules across three lists:
- **always_deny**: Permanently blocked tools/commands
- **always_ask**: Always prompt (even in ACTIVE mode) - for critical commands
- **always_allow**: Auto-approved tools/commands

Use Tab/Shift+Tab to switch tabs, arrow keys to navigate, `d` to delete, `e` to edit in editor.

</details>

### Utilities

<details>
<summary><code>/todo [N]</code> - View current todo list</summary>

Shows the current todo list. Specify optional number to limit displayed items (default: 10).

```bash
/todo       # Show max 10 items
/todo 20    # Show max 20 items
```

</details>

<details>
<summary><code>/graph [--browser]</code> - Visualize agent graph</summary>

Renders in terminal (ASCII) or opens in browser with `--browser` flag.

</details>

<details>
<summary><code>/help</code> - Show help</summary>

</details>

<details>
<summary><code>/exit</code> - Exit application (or double Ctrl+C)</summary>

</details>

## Usage

Configs are auto-generated in `.langrepl/` on first run.

### Agents

`.langrepl/agents/*.yml`:
```yaml
# agents/my-agent.yml (filename must match agent name)
version: 2.2.0
name: my-agent
prompt: prompts/my_agent.md  # Single file or array of files
llm: haiku-4.5               # References llms/*.yml
checkpointer: sqlite         # References checkpointers/*.yml
recursion_limit: 40
default: true
tools:
  patterns:
    - impl:file_system:read_file
    - mcp:context7:resolve-library-id
  use_catalog: false         # Use tool catalog to reduce token usage
  output_max_tokens: 10000   # Max tokens per tool output
skills:
  patterns:
    - general:skill-creator  # References skills/<category>/<name>
subagents:
  - general-purpose          # References subagents/*.yml
compression:
  auto_compress_enabled: true
  auto_compress_threshold: 0.8
  llm: haiku-4.5
  prompt:
    - prompts/shared/general_compression.md
    - prompts/suffixes/environments.md
  messages_to_keep: 0  # Keep N recent messages verbatim during compression
sandboxes:                    # See Sandboxes section
  enabled: true
  profiles:
    - sandbox: rw-online-macos
      patterns: [impl:*:*, "!impl:terminal:*"]
    - sandbox: null            # Bypass for excluded tools
      patterns: [impl:terminal:*, mcp:*:*]
```

<details>
<summary>Single-file format: .langrepl/config.agents.yml</summary>

```yaml
agents:
  - version: 2.2.0
    name: my-agent
    prompt: prompts/my_agent.md
    llm: haiku-4.5
    checkpointer: sqlite
    recursion_limit: 40
    default: true
    tools:
      patterns:
        - impl:file_system:read_file
        - mcp:context7:resolve-library-id
      use_catalog: false         # Use tool catalog to reduce token usage
      output_max_tokens: 10000   # Max tokens per tool output
    skills:
      patterns:
        - general:skill-creator  # References skills/<category>/<name>
    subagents:
      - general-purpose
    compression:
      auto_compress_enabled: true
      auto_compress_threshold: 0.8
      llm: haiku-4.5
      prompt:
        - prompts/shared/general_compression.md
        - prompts/suffixes/environments.md
      messages_to_keep: 0  # Keep N recent messages verbatim during compression
```

</details>

**Tool naming**: `<category>:<module>:<function>` with wildcard (`*`, `?`, `[seq]`) and negative (`!`) pattern support
- `impl:*:*` - All built-in tools
- `impl:file_system:read_*` - All read_* tools in file_system
- `!impl:file_system:write_*` - Exclude write_* tools
- `mcp:server:*` - All tools from MCP server

**Tool catalog**: When `use_catalog: true`, impl/mcp tools are wrapped in a unified catalog interface to reduce token usage. The agent receives catalog tools instead of individual tool definitions.

#### Available Tools

<details>
<summary><strong>impl:file_system</strong> - File operations</summary>

| Tool | Pattern | Description |
|------|---------|-------------|
| `read_file` | `impl:file_system:read_file` | Read file content with line-based pagination |
| `write_file` | `impl:file_system:write_file` | Create a new file with content |
| `edit_file` | `impl:file_system:edit_file` | Edit a file by replacing old content with new content |
| `create_dir` | `impl:file_system:create_dir` | Create a directory recursively |
| `move_file` | `impl:file_system:move_file` | Move a file from source to destination |
| `move_multiple_files` | `impl:file_system:move_multiple_files` | Move multiple files in one operation |
| `delete_file` | `impl:file_system:delete_file` | Delete a file |
| `delete_dir` | `impl:file_system:delete_dir` | Delete a directory recursively |
| `insert_at_line` | `impl:file_system:insert_at_line` | Insert content at a specific line number |

</details>

<details>
<summary><strong>impl:grep_search</strong> - Code search</summary>

| Tool | Pattern | Description |
|------|---------|-------------|
| `grep_search` | `impl:grep_search:grep_search` | Search for code using ripgrep-compatible Rust regex patterns |

</details>

<details>
<summary><strong>impl:terminal</strong> - Terminal commands</summary>

| Tool | Pattern | Description |
|------|---------|-------------|
| `run_command` | `impl:terminal:run_command` | Execute terminal commands |
| `get_directory_structure` | `impl:terminal:get_directory_structure` | Get a tree view of directory structure |

</details>

<details>
<summary><strong>impl:web</strong> - Web operations</summary>

| Tool | Pattern | Description |
|------|---------|-------------|
| `fetch_web_content` | `impl:web:fetch_web_content` | Fetch webpage main content as markdown |

</details>

<details>
<summary><strong>internal:memory</strong> - Virtual filesystem for agent state</summary>

| Tool | Pattern | Description |
|------|---------|-------------|
| `list_memory_files` | `internal:memory:list_memory_files` | List all files in virtual memory filesystem |
| `read_memory_file` | `internal:memory:read_memory_file` | Read memory file content with pagination |
| `write_memory_file` | `internal:memory:write_memory_file` | Create or overwrite a memory file |
| `edit_memory_file` | `internal:memory:edit_memory_file` | Edit a memory file by replacing content |

</details>

<details>
<summary><strong>internal:todo</strong> - Task management</summary>

| Tool | Pattern | Description |
|------|---------|-------------|
| `write_todos` | `internal:todo:write_todos` | Create and manage structured task lists |
| `read_todos` | `internal:todo:read_todos` | Read the current TODO list |

</details>

<details>
<summary><strong>subagents</strong> - Agent delegation (auto-injected when <code>subagents:</code> exists)</summary>

| Tool | Description |
|------|-------------|
| `task` | Delegate a task to a specialized sub-agent |
| `think` | Strategic reflection on progress and decision-making |

</details>

<details>
<summary><strong>skills</strong> - Skill discovery (auto-injected when <code>skills.use_catalog: true</code>)</summary>

| Tool | Description |
|------|-------------|
| `fetch_skills` | Discover and search for available skills |
| `get_skill` | Read the full content of a specific skill |

</details>

<details>
<summary><strong>catalog</strong> - Tool discovery (auto-injected when <code>tools.use_catalog: true</code>)</summary>

| Tool | Description |
|------|-------------|
| `fetch_tools` | Discover and search for available tools |
| `get_tool` | Get tool documentation and parameters |
| `run_tool` | Execute a tool from the catalog |

</details>

### Custom Prompts

Place prompts in `.langrepl/prompts/`:
```markdown
# prompts/my_agent.md
You are a helpful assistant...

{user_memory}
```

**Placeholders:**
- `{user_memory}` - Auto-appended if missing
- `{conversation}` - Auto-wrapped if missing (compression prompts only)

### LLMs

`.langrepl/llms/*.yml`:
```yaml
# llms/anthropic.yml (organize by provider, filename is flexible)
- version: 1.0.0
  model: claude-haiku-4-5
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
  - version: 1.0.0
    model: claude-haiku-4-5
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
version: 1.0.0
type: sqlite
max_connections: 10
```

```yaml
# checkpointers/memory.yml (filename must match checkpointer type)
version: 1.0.0
type: memory
max_connections: 1
```

<details>
<summary>Single-file format: .langrepl/config.checkpointers.yml</summary>

```yaml
checkpointers:
  - version: 1.0.0
    type: sqlite
    max_connections: 10
  - version: 1.0.0
    type: memory
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
version: 2.0.0
name: code-reviewer
prompt: prompts/code-reviewer.md
llm: haiku-4.5
tools:
  patterns: [impl:file_system:read_file]
  use_catalog: false
  output_max_tokens: 10000
```

<details>
<summary>Single-file format: .langrepl/config.subagents.yml</summary>

```yaml
agents:
  - version: 2.0.0
    name: code-reviewer
    prompt: prompts/code-reviewer.md
    llm: haiku-4.5
    tools:
      patterns: [impl:file_system:read_file]
      use_catalog: false
      output_max_tokens: 10000
```

</details>

**Add custom**: Create prompt, add config file, reference in parent agent's `subagents` list.

### Custom Tools

1. Implement in `src/langrepl/tools/impl/my_tool.py`:
   ```python
   from langchain.tools import tool

   @tool()
   def my_tool(query: str) -> str:
       """Tool description."""
       return result
   ```

2. Register in `src/langrepl/tools/factory.py`:
   ```python
   MY_TOOLS = [my_tool]
   self.impl_tools.extend(MY_TOOLS)
   ```

3. Reference: `impl:my_tool:my_tool`

### Skills

Skills are modular knowledge packages that extend agent capabilities. See [anthropics/skills](https://github.com/anthropics/skills) for details.

**Directory structure** (`.langrepl/skills/`):

```text
skills/
├── general/
│   └── skill-creator/
│       ├── SKILL.md            # Required: metadata and instructions
│       ├── scripts/            # Optional: executable code
│       ├── references/         # Optional: documentation
│       └── assets/             # Optional: templates, images, etc.
└── custom-category/
    └── my-skill/
        └── SKILL.md
```

**Skill naming**: `<category>:<name>` with wildcard (`*`) and negative (`!`) pattern support
- `general:skill-creator` - Specific skill
- `general:*` - All skills in category
- `!general:dangerous-skill` - Exclude specific skill
- `*:*` - All skills

**Built-in**: [skill-creator](https://www.aitmpl.com/component/skill/skill-creator) - Guide for creating custom skills

### MCP Servers (`config.mcp.json`)

```json
{
  "mcpServers": {
    "my-server": {
      "command": "uvx",
      "args": ["my-mcp-package"],
      "transport": "stdio",
      "enabled": true,
      "stateful": false,
      "include": ["tool1"],
      "exclude": [],
      "repair_command": ["rm", "-rf", ".some_cache"],
      "repair_timeout": 30,
      "invoke_timeout": 60.0
    },
    "remote-server": {
      "url": "http://localhost:8080/mcp",
      "transport": "http",
      "timeout": 30,
      "sse_read_timeout": 300,
      "invoke_timeout": 60.0
    }
  }
}
```

- `transport`: `stdio` (local command), `http` (HTTP/streamable), `sse` (Server-Sent Events), `websocket`. Aliases `streamable_http` and `streamable-http` map to `http`.
- `timeout`, `sse_read_timeout`: Connection and SSE read timeouts in seconds (for HTTP-based transports)
- `stateful`: Keep connection alive between tool calls (default: `false`). Use for servers that need persistent state.
- `repair_command`: Command array to run if server fails (default: none). Auto-retries after repair.
- `repair_timeout`: Repair command timeout in seconds (default: `30` when `repair_command` is set)
- `invoke_timeout`: Tool invocation timeout in seconds (default: none)
- Suppress stderr: `"command": "sh", "args": ["-c", "npx pkg 2>/dev/null"]`
- Reference: `mcp:my-server:tool1`
- Examples: [useful-mcp-servers.json](examples/useful-mcp-servers.json)

### Tool Approval (`config.approval.json`)

```json
{
  "always_allow": [
    { "name": "read_file", "args": null }
  ],
  "always_deny": [
    { "name": "run_command", "args": { "command": "rm -rf /.*" } }
  ],
  "always_ask": [
    { "name": "run_command", "args": { "command": "rm\\s+-rf.*" } },
    { "name": "run_command", "args": { "command": "git\\s+push.*" } },
    { "name": "run_command", "args": { "command": "git\\s+reset\\s+--hard.*" } },
    { "name": "run_command", "args": { "command": "sudo\\s+.*" } }
  ]
}
```

**Three rule lists:**
- `always_deny` - Permanently blocked (highest priority)
- `always_ask` - Always prompt, even in ACTIVE mode (for critical commands)
- `always_allow` - Auto-approved

**Modes and behavior:**

| Mode | `always_deny` | `always_ask` | `always_allow` | No match |
|------|---------------|--------------|----------------|----------|
| `SEMI_ACTIVE` | Block | Prompt | Allow | Prompt |
| `ACTIVE` | Block | Prompt | Allow | Auto-allow |
| `AGGRESSIVE` | Block | Auto-allow | Allow | Auto-allow |

Default `always_ask` rules protect against destructive commands like `rm -rf`, `git push`, `git reset --hard`, and `sudo`.

### Sandboxes (Beta)

Sandboxes provide secure, isolated execution environments for tools. They restrict filesystem access, network connectivity, and system calls to prevent potentially dangerous operations.

**Prerequisites:**
- **macOS**: Built-in `sandbox-exec` (no installation needed)
- **Linux**: `bubblewrap` package required (see [Prerequisites](#prerequisites))

`.langrepl/sandboxes/*.yml`:
```yaml
# sandboxes/rw-online-macos.yml (filename must match sandbox name)
version: "1.0.0"
name: rw-online-macos
type: seatbelt      # macOS: seatbelt, Linux: bubblewrap
os: macos           # macos or linux

filesystem:
  read:
    - "."           # Working directory
    - "/usr"        # System binaries
    - "~/.local"    # User tools (uvx, pipx)
  write:
    - "."
    - "/private/tmp"
  hidden:           # Blocked paths (glob patterns)
    - ".env"
    - "~/.ssh"
    - "*.pem"

network:
  remote:
    - "*"           # "*" = allow all, [] = deny all
  local: []         # Unix sockets
```

**Default profiles** (auto-copied per platform on first run):

| Profile | Filesystem | Network | Use Case |
|---------|------------|---------|----------|
| `rw-online-{os}` | Read/Write | Yes | General development |
| `rw-offline-{os}` | Read/Write | No | Sensitive data |
| `ro-online-{os}` | Read-only | Yes | Code exploration |
| `ro-offline-{os}` | Read-only | No | Maximum isolation |

**Notes:**
- **Package managers:** `uvx`, `npx`, `pip` may need network to check/download from registries. Default profiles include `~/.cache/uv`, `~/.npm`, `~/.local` for caching. Offline sandboxes auto-inject `NPM_CONFIG_OFFLINE=true` and `UV_OFFLINE=1` for MCP servers.
- **Docker/containers:** Docker CLI requires socket access. Add to `network.local`: Docker Desktop (`/var/run/docker.sock`), OrbStack (`~/.orbstack/run/docker.sock`), Rancher Desktop (`~/.rd/docker.sock`), Colima (`~/.colima/default/docker.sock`).
- **MCP servers:** Sandboxed at startup (command wrapped). Match with `mcp:server-name:*` (tool part must be `*`). HTTP servers require explicit bypass (`sandbox: null`).
- **Sandbox patterns:** Support negative patterns. Use `!mcp:server:*` to exclude from a wildcard match. Tools/servers must match exactly one profile or they're blocked.
- **Working directory (`"."`):** When included, mounted and used as cwd. When excluded: Linux = not mounted, cwd is `/` inside tmpfs; macOS = can list files but cannot read contents.
- **Symlinks:** Symlinks resolving outside allowed boundaries are blocked. Warnings logged at startup. Add targets to `filesystem.read` if needed.

**Limitations:**
- **Network (remote):** Binary - `["*"]` allows all TCP/UDP, `[]` blocks all. `["*"]` reserved for future domain filtering.
- **Network (local):** macOS = allowlist-based. Linux = binary (empty blocks all, any entry allows all); per-socket filtering reserved for future.
- **macOS (Seatbelt):** Deny-by-default policy. Mach services allowed for DNS, TLS, keychain.
- **Linux (Bubblewrap):** Namespace isolation (user, pid, ipc, uts, network). `pyseccomp` optional for syscall blocking.
- **Other:** Sandbox worker only executes built-in tools (from `langrepl.tools.*` module). 60s timeout. 10MB stdout / 1MB stderr limits. Hidden patterns use gitignore-style glob.

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
