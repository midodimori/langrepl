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
- [Usage](#usage)
    - [Agents](#agents-configagentsyml)
    - [LLMs](#llms-configllmsyml)
    - [Custom Tools](#custom-tools)
    - [MCP Servers](#mcp-servers-configmcpjson)
    - [Sub-Agents](#sub-agents-configsubagentsyml)
    - [Tool Approval](#tool-approval-configapprovaljson)
- [Development](#development)
- [License](#license)

## Features

- **[Deep Agent Architecture](https://blog.langchain.com/deep-agents/)** - Planning tools, virtual filesystem, and
  sub-agent delegation for complex multi-step tasks
- **LangGraph Server Mode** - Run agents as API servers with LangGraph Studio integration for visual debugging
- **Multi-Provider LLM Support** - OpenAI, Anthropic, Google, AWS Bedrock, Ollama, DeepSeek, ZhipuAI, and local models (LMStudio, Ollama)
- **Extensible Tool System** - File operations, web search, terminal access, grep search, and MCP server integration
- **Persistent Conversations** - SQLite-backed thread storage with resume, replay, and compression
- **User Memory** - Project-specific custom instructions and preferences that persist across conversations
- **Human-in-the-Loop** - Configurable tool approval system with regex-based allow/deny rules
- **Cost Tracking (Beta)** - Token usage and cost calculation per conversation
- **MCP Server Support** - Integrate external tool servers via the MCP protocol

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
make install
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
make install
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

## Usage

Configs are auto-generated in `.langrepl/` on first run.

### Agents (`config.agents.yml`)

```yaml
agents:
  - name: my-agent
    prompt: prompts/my_agent.md  # Single file or array of files, this will look for `.langrepl/prompts/my_agent.md`
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

**Tool naming**: `<category>:<module>:<function>` with wildcard support (`*`, `?`, `[seq]`)
- `impl:*:*` - All built-in tools
- `impl:file_system:read_*` - All read_* tools in file_system
- `mcp:server:*` - All tools from MCP server

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

### Custom Tools

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
      "repair_command": ["sh", "-c", "rm -rf .some_cache"]
    }
  }
}
```

- `repair_command`: Runs if server fails, then run this command before retrying
- Suppress stderr: `"command": "sh", "args": ["-c", "npx pkg 2>/dev/null"]`
- Reference: `mcp:my-server:tool1`
- Examples: [useful-mcp-servers.json](examples/useful-mcp-servers.json)

### Sub-Agents (`config.subagents.yml`)

Sub-agents use the same config structure as main agents.

```yaml
subagents:
  - name: code-reviewer
    prompt: prompts/code-reviewer.md
    tools: [impl:file_system:read_file]
```

**Add custom**: Create prompt, add to config above, reference in parent agent's `subagents` list.

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

```bash
make install      # Install dependencies + pre-commit hooks
make lint-fix     # Format and lint code
make test         # Run tests
make pre-commit   # Run pre-commit on all files
make bump-patch   # Bump version (0.1.0 → 0.1.1)
make clean        # Remove cache/build artifacts
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
