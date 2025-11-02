# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2025-11-02

### Features

- Add @ reference completion for file paths ([#16](https://github.com/midodimori/langrepl/pull/16))

## [0.2.4] - 2025-10-31

### Code Refactoring

- Standardize key bindings to use Keys enum constants ([#12](https://github.com/midodimori/langrepl/pull/12))

### Bug Fixes

- Improve tool error handling and replay checkpoint deletion ([#13](https://github.com/midodimori/langrepl/pull/13))

## [0.2.3] - 2025-10-29

### Tests

- Add integration tests for tools ([#11](https://github.com/midodimori/langrepl/pull/11))

## [0.2.2] - 2025-10-29

### Code Refactoring

- Flatten tool parameters ([#10](https://github.com/midodimori/langrepl/pull/10))

## [0.2.1] - 2025-10-29

### Bug Fixes

- Add missing injected params to EditMemoryFileInput ([#9](https://github.com/midodimori/langrepl/pull/9))

## [0.2.0] - 2025-10-29

### Features

- Add model switching for subagents ([#8](https://github.com/midodimori/langrepl/pull/8))

## [0.1.1] - 2025-10-28

### Features

- Add support for zhipuai glm ([#1](https://github.com/midodimori/langrepl/pull/1))
- Automate version bumping via GitHub Actions ([#6](https://github.com/midodimori/langrepl/pull/6))

### Bug Fixes

- Add write permissions to version bump workflow ([#7](https://github.com/midodimori/langrepl/pull/7))

## [0.1.0] - 2025-10-06

Initial release of LangREPL - an interactive terminal CLI for working with LLM agents.

### Features

- ReAct agent pattern with tool execution
- Multi-provider LLM support (OpenAI, Anthropic, Google, AWS Bedrock, Ollama, DeepSeek, Zhipu AI)
- Persistent conversation threads with SQLite checkpointer
- Extensible tool system (filesystem, web, grep, terminal)
- MCP (Model Context Protocol) integration
- Human-in-the-loop tool approval system
- Agent switching and configuration
- Virtual filesystem for document drafting
- Task planning with todo tracking
- LangGraph server mode
