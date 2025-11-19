# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.6.0](https://github.com/midodimori/langrepl/compare/v1.5.0...v1.6.0) (2025-11-19)


### Features

* add message indexing for resume/replay performance ([#49](https://github.com/midodimori/langrepl/issues/49)) ([1a06163](https://github.com/midodimori/langrepl/commit/1a061633bcd142038a2483ad567f8b11148b584e))


### Bug Fixes

* disable attestations for TestPyPI to avoid conflicts ([abcfcd2](https://github.com/midodimori/langrepl/commit/abcfcd2b6297a35bfc4c3e8f74c4892254afba58))
* skip TestPyPI if version already exists ([a448c49](https://github.com/midodimori/langrepl/commit/a448c4961b79b1d3b2cfbdb0ea6e97b0cedcddca))

## [1.5.0](https://github.com/midodimori/langrepl/compare/v1.4.1...v1.5.0) (2025-11-17)


### Features

* Add streaming ([#46](https://github.com/midodimori/langrepl/issues/46)) ([b94daf8](https://github.com/midodimori/langrepl/commit/b94daf8c54cdcff0ff1d1b388ddf25511911021a))

## [1.4.1](https://github.com/midodimori/langrepl/compare/v1.4.0...v1.4.1) (2025-11-15)


### Bug Fixes

* wrap Path.glob() in asyncio.to_thread() to prevent BlockingError in server mode ([9a4f7ee](https://github.com/midodimori/langrepl/commit/9a4f7ee766d1a122dfa5096c112e4d37c2788394))


### Documentation

* update ([af8607d](https://github.com/midodimori/langrepl/commit/af8607d00ed4b181e397d905c719490120d8d878))

## [1.4.0](https://github.com/midodimori/langrepl/compare/v1.3.0...v1.4.0) (2025-11-11)


### Features

* add one-shot mode ([#40](https://github.com/midodimori/langrepl/issues/40)) ([43cb1de](https://github.com/midodimori/langrepl/commit/43cb1de82de32a2c7c6ac6642f6c3a9d2ef4b44c))


### Documentation

* update ([4f83edb](https://github.com/midodimori/langrepl/commit/4f83edb8422f0a05d3ef279b8f63ada83d8097bb))

## [1.3.0](https://github.com/midodimori/langrepl/compare/v1.2.1...v1.3.0) (2025-11-10)


### Features

* add multimodal image support with builder pattern ([#37](https://github.com/midodimori/langrepl/issues/37)) ([dc3a94f](https://github.com/midodimori/langrepl/commit/dc3a94fbe4d0ac6ce101b813775e2ecebac79071))


### Documentation

* update demo ([799001d](https://github.com/midodimori/langrepl/commit/799001dfe87a64e617ce09bec17cf3d4fc21e512))

## [1.2.1](https://github.com/midodimori/langrepl/compare/v1.2.0...v1.2.1) (2025-11-09)


### Bug Fixes

* add short content for task tool result ([2e094ad](https://github.com/midodimori/langrepl/commit/2e094ad9f6ea22e763d3847cfcc72f1eb4cc554a))
* always return short_content in task tool ([bc1200d](https://github.com/midodimori/langrepl/commit/bc1200da099a0c415f78b32b48bfa6970e96aad6))

## [1.2.0](https://github.com/midodimori/langrepl/compare/v1.1.3...v1.2.0) (2025-11-09)


### Features

* add model indicators in /model selector ([3dbe31f](https://github.com/midodimori/langrepl/commit/3dbe31f8a5d65b9a65bfeeae080df08f6b90b6ae))

## [1.1.3](https://github.com/midodimori/langrepl/compare/v1.1.2...v1.1.3) (2025-11-09)


### Bug Fixes

* add cache for approval to prevent duplication ([b99f972](https://github.com/midodimori/langrepl/commit/b99f9721ecac55e6c6907767475b6811ad7985dc))

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
