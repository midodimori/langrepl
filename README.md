# Langrepl

Interactive terminal CLI for building and running LLM agents. Built with LangChain, LangGraph, Prompt Toolkit, and Rich.

https://github.com/user-attachments/assets/5d95e221-3883-44f8-9694-74c5e215b4e2

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
    - [Option 1: Install from GitHub (Quickest)](#option-1-install-from-github-quickest)
    - [Option 2: Install Globally (For Development)](#option-2-install-globally-for-development)
    - [Option 3: Local Development](#option-3-local-development)
    - [Configure API Keys](#configure-api-keys)
    - [Tracing](#tracing)
- [Quick Start](#quick-start)
    - [Interactive Chat Mode (Default)](#interactive-chat-mode-default)
    - [LangGraph Server Mode](#langgraph-server-mode)
- [Interactive Commands](#interactive-commands)
    - [Conversation Management](#conversation-management)
    - [Configuration](#configuration)
    - [Utilities](#utilities)
- [Configuration](#configuration-1)
    - [Agents](#agents-configagentsyml)
    - [LLMs](#llms-configllmsyml)
    - [MCP Servers](#mcp-servers-configmcpjson)
    - [Tool Approval](#tool-approval-configapprovaljson)
- [Architecture](#architecture)
    - [Core Components](#core-components)
- [Development](#development)
- [Extending Langrepl](#extending-langrepl)
    - [Add a Custom Agent](#add-a-custom-agent)
    - [Add a Custom Tool](#add-a-custom-tool)
    - [Add an MCP Server](#add-an-mcp-server)
    - [Add a Sub-Agent](#add-a-sub-agent)
- [Documentation](#documentation)
- [License](#license)

## Features

- **[Deep Agent Architecture](https://blog.langchain.com/deep-agents/)** - Planning tools, virtual filesystem, and
  sub-agent delegation for complex multi-step tasks
- **LangGraph Server Mode** - Run agents as API servers with LangGraph Studio integration for visual debugging
- **Multi-Provider LLM Support** - OpenAI, Anthropic, Google, AWS Bedrock, Ollama, DeepSeek
- **Extensible Tool System** - File operations, web search, terminal access, grep search, and MCP server integration
- **Persistent Conversations** - SQLite-backed thread storage with resume, replay, and compression
- **User Memory** - Project-specific custom instructions and preferences that persist across conversations
- **Human-in-the-Loop** - Configurable tool approval system with regex-based allow/deny rules
- **Cost Tracking (Beta)** - Token usage and cost calculation per conversation

## Prerequisites

- **Python 3.13+** - Required for the project
- **uv** - Fast Python package
  installer ([install instructions](https://docs.astral.sh/uv/getting-started/installation/))
- **ripgrep (rg)** - Fast search tool used by the grep_search functionality:
    - macOS: `brew install ripgrep`
    - Ubuntu/Debian: `sudo apt install ripgrep`
    - Arch Linux: `sudo pacman -S ripgrep`
    - Windows: `choco install ripgrep` or download from [releases](https://github.com/BurntSushi/ripgrep/releases)
- **Node.js & npm** (optional) - Required only if using MCP servers that run via npx

## Installation

### Option 1: Install from GitHub (Quickest)

Install directly from GitHub without cloning:

```bash
uvx --from git+https://github.com/midodimori/langrepl lg
```

Or for persistent installation:

```bash
uv tool install git+https://github.com/midodimori/langrepl
```

After persistent installation:

```bash
langrepl          # Start interactive session
lg                # Quick alias
```

### Option 2: Install Globally (For Development)

Install langrepl globally to use `langrepl` or `lg` commands anywhere:

```bash
git clone https://github.com/midodimori/langrepl.git
cd langrepl
uv tool install --editable .
```

After installation, commands are available globally:

```bash
langrepl          # Start interactive session
lg                # Quick alias
```

### Option 3: Local Development

For local development without global installation:

```bash
git clone https://github.com/midodimori/langrepl.git
cd langrepl
uv sync
```

Then run with:

```bash
uv run langrepl   # or: uv run lg
```

### Configure API Keys

Set API keys via `.env`:

```bash
LLM__OPENAI_API_KEY=your_openai_api_key_here
LLM__ANTHROPIC_API_KEY=your_anthropic_api_key_here
LLM__GOOGLE_API_KEY=your_google_api_key_here
LLM__DEEPSEEK_API_KEY=your_deepseek_api_key_here
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

### Interactive Chat Mode (Default)

```bash
# Start interactive session (uses general agent by default)
uv run langrepl

# Use specific agent
uv run langrepl -a general

# Resume last conversation
uv run langrepl -r

# Set approval mode (SEMI_ACTIVE, ACTIVE, AGGRESSIVE)
uv run langrepl -am ACTIVE

# Quick alias
uv run lg
```

### LangGraph Server Mode

Run your agent as a LangGraph server for integration with LangGraph Studio:

```bash
# Start LangGraph server with specific agent
uv run langrepl -s -a general

# Server will start at http://localhost:2024
# Studio UI: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
# API Docs: http://localhost:2024/docs

# Set approval mode for server
uv run langrepl -s -a general -am ACTIVE
```

The server mode:

- Generates `langgraph.json` configuration automatically
- Creates/updates assistants via the LangGraph API
- Enables visual debugging through LangGraph Studio
- Supports all agent configurations and MCP servers

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

## Configuration

Configs are auto-generated in `.langrepl/` on first run. Customize by editing these files:

### Agents (`config.agents.yml`)

```yaml
agents:
  - name: my-agent
    prompt: prompts/my_agent.md  # Single file or array of files
    llm: haiku-4.5
    checkpointer: sqlite
    recursion_limit: 40
    tool_output_max_tokens: 10000 # If set, this defines max tokens from tool outputs, if exceeded, output is saved to virtual fs, the agent need to have internal:memory:read_memory_file tool to read it.
    default: true                  # Set to true to make this the default agent
    tools:
      - impl:file_system:read_file          # Built-in tool
      - impl:web:fetch_web_content          # Built-in tool
      - mcp:context7:resolve-library-id     # MCP tool
      - mcp:context7:get-library-docs       # MCP tool
    subagents:
      - general-purpose
      - explorer
    compression:
      auto_compress_enabled: true
      auto_compress_threshold: 0.8
      compression_llm: haiku-4.5
```

**Tool naming pattern**: `<category>:<module>:<function>`

- `impl:` - Built-in user-facing tools
- `internal:` - Agent-only tools (memory, todo)
- `mcp:<server>:<tool>` - MCP server tools

**Wildcard support**: Both `<module>` and `<function>` support wildcard patterns:

- `*` - Matches everything
- `?` - Matches any single character
- `[seq]` - Matches any character in seq
- `[!seq]` - Matches any character not in seq

Examples:

- `impl:*:*` - All impl tools
- `impl:file_system:*` - All file_system tools
- `impl:file_system:read_*` - All file_system read_* tools
- `impl:*:read_*` - All read_* tools across all modules
- `impl:*:*multiple*` - All tools with "multiple" in the name
- `mcp:context7:*` - All tools from context7 MCP server

### LLMs (`config.llms.yml`)

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

### MCP Servers (`config.mcp.json`)

```json
{
  "mcpServers": {
    "context7": {
      "command": "sh",
      "args": [
        "-c",
        "npx -y @upstash/context7-mcp --api-key YOUR_API_KEY 2>/dev/null"
      ],
      "transport": "stdio",
      "enabled": true,
      "include": [
        "resolve-library-id",
        "get-library-docs"
      ],
      "exclude": []
    }
  }
}
```

Reference MCP tools in agent config: `mcp:<server-name>:<tool-name>`

### Tool Approval (`config.approval.json`)

```json
{
  "always_allow": [
    "impl:file_system:read_file",
    "impl:web:fetch_web_content"
  ],
  "always_deny": [
    "impl:terminal:run_command:rm -rf"
  ]
}
```

Approval modes:

- **SEMI_ACTIVE** - Ask for approval unless whitelisted
- **ACTIVE** - Auto-approve except denied patterns
- **AGGRESSIVE** - Bypass all approval

## Architecture

### Core Components

**Agents** (`src/agents/`)

- ReAct Agent - Core reasoning and acting loop
- Deep Agent - Extended with planning, memory, and sub-agents
- Factory Pattern - Builds agents from YAML configs

**Tools** (`src/tools/`)

- `impl/` - User-facing: file_system, web, grep_search, terminal
- `internal/` - Agent-only: memory (virtual fs), todo (planning)
- `subagents/` - Task delegation
- `mcp/` - External tools via Model Context Protocol

**State** (`src/state/`)

- `messages` - Conversation history
- `todos` - Task tracking
- `files` - Virtual filesystem
- Token and cost tracking

**Checkpointers** (`src/checkpointer/`)

- SQLite - Persistent storage (`.langrepl/checkpoints.db`)
- Memory - Ephemeral storage

**MCP** (`src/mcp/`)

- Tool filtering per server
- Multiple transports (stdio, streamable_http)
- Auto proxy injection

## Development

```bash
# Format and lint
make lint-fix

# Test
make test
```

## Extending Langrepl

### Add a Custom Agent

1. Create prompt: `resources/configs/default/prompts/researcher.md`
2. Add to `config.agents.yml`:
   ```yaml
   agents:
     - name: researcher
       prompt: prompts/researcher.md
       llm: haiku-4.5
       tools: [impl:web:fetch_web_content]
   ```

### Add a Custom Tool

1. Implement in `src/tools/impl/my_tool.py`:
   ```python
   from src.tools.wrapper import approval_tool

   @approval_tool()
   def my_tool(query: str) -> str:
       """Tool description."""
       return result
   ```

2. Register in `src/tools/factory.py`:
   ```python
   MY_TOOLS = [my_tool]
   self.impl_tools.extend(MY_TOOLS)
   ```

3. Add to agent config:
   ```yaml
   tools:
     - impl:my_tool:my_tool
   ```

### Add an MCP Server

1. Add to `config.mcp.json`:
   ```json
   {
     "mcpServers": {
       "my-server": {
         "command": "uvx",
         "args": ["my-mcp-package"],
         "enabled": true
       }
     }
   }
   ```
   For suppressing output noise, redirect stderr to `/dev/null` with `2>/dev/null` in the command:
   ```json
   {
      "mcpServers": {
        "my-server": {
          "command": "sh",
          "args": [
            "-c",
            "npx -y <my-server-lib> 2>/dev/null"
          ]
        }
      }
    }
   ```
   See [MCP Examples](examples/useful-mcp-servers.json) for some useful MCP server implementations.


2. Reference in agent config:
   ```yaml
   tools:
     - mcp:my-server:tool_name
   ```

### Add a Sub-Agent

1. Create prompt: `resources/configs/default/prompts/code-reviewer.md`
2. Add to `config.subagents.yml`:
   ```yaml
   subagents:
     - name: code-reviewer
       prompt: prompts/code-reviewer.md
       tools: [impl:file_system:read_file]
   ```

3. Reference in parent agent:
   ```yaml
   subagents:
     - code-reviewer
   ```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.