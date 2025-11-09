# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.2](https://github.com/midodimori/langrepl/compare/v1.1.1...v1.1.2) (2025-11-09)


### Bug Fixes

* restore stable state by reverting recent changes ([121d003](https://github.com/midodimori/langrepl/commit/121d003dffc8e9574a8ac86189580856fd8368a6))

## [1.0.2](https://github.com/midodimori/langrepl/compare/v1.0.1...v1.0.2) (2025-11-07)


### Bug Fixes

* input tokens count ([822f45c](https://github.com/midodimori/langrepl/commit/822f45ce13a60fe3b751c74eb6cd0098ae2382f4))

## [1.0.1](https://github.com/midodimori/langrepl/compare/v1.0.0...v1.0.1) (2025-11-07)


### Bug Fixes

* render interrupt ([ae07b44](https://github.com/midodimori/langrepl/commit/ae07b44fc660b53540deb0a41289325da2aca032))

## [1.0.0](https://github.com/midodimori/langrepl/compare/v0.3.1...v1.0.0) (2025-11-07)


### ⚠ BREAKING CHANGES

* Major upgrade from LangChain 0.x to 1.x with architectural changes

### Features

* migrate to LangChain v1.0 with context-based architecture ([#20](https://github.com/midodimori/langrepl/issues/20)) ([d003cce](https://github.com/midodimori/langrepl/commit/d003cce49694ce0140249386db96b655dbe58fa0))


### Bug Fixes

* correct ToolRuntime context type and auto-approve internal tools ([8d17619](https://github.com/midodimori/langrepl/commit/8d176190a4499dd3d66b74d56fda8643154ef623))

## [0.3.1](https://github.com/midodimori/langrepl/compare/v0.3.0...v0.3.1) (2025-11-05)


### Code Refactoring

* **cli:** reorganize bootstrap layer and expand tests ([#18](https://github.com/midodimori/langrepl/pull/18)) ([7ede2de](https://github.com/midodimori/langrepl/commit/7ede2de6f83cf101df18ab1141b3831ee056c75d))

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
