# CHANGELOG

<!-- version list -->

## v1.9.2 (2025-12-08)

### Bug Fixes

- Simplify prompt loading in compression handler (#62)
  ([#62](https://github.com/midodimori/langrepl/pull/62),
  [`5801b92`](https://github.com/midodimori/langrepl/commit/5801b9269b9c7badf907d503a7b9fc76fc68eabe))


## v1.9.1 (2025-12-05)

### Bug Fixes

- Default prompt path
  ([`f9da498`](https://github.com/midodimori/langrepl/commit/f9da498fddfc26bc5d2555bb3a1de1530b671ef4))


## v1.9.0 (2025-12-05)

### Features

- Enhance compression with configurable prompts and markdown formatting (#61)
  ([#61](https://github.com/midodimori/langrepl/pull/61),
  [`e2b4fe2`](https://github.com/midodimori/langrepl/commit/e2b4fe254aeba2fffabbf3640d3b62750efd9215))


## v1.8.6 (2025-12-03)

### Bug Fixes

- Sort edit diffs by line position for correct display order + ctrl c for cancellation + pending
  tool calls (#60) ([#60](https://github.com/midodimori/langrepl/pull/60),
  [`b5f6991`](https://github.com/midodimori/langrepl/commit/b5f6991c15a6a7689d8714d49c9a6a06a57adbb9))


## v1.8.5 (2025-11-30)

### Bug Fixes

- Use async for skills loading
  ([`d98a91b`](https://github.com/midodimori/langrepl/commit/d98a91b842137f8a5beb968a3d0320f7a96ef81a))


## v1.8.4 (2025-11-30)

### Features

- Pretty format for todos list
  ([`bb03ac7`](https://github.com/midodimori/langrepl/commit/bb03ac74015de18068ad29214498e31ed8df45ee))


## v1.8.3 (2025-11-30)


## v1.8.2 (2025-11-30)

### Performance Improvements

- Reduce startup time (#58) ([#58](https://github.com/midodimori/langrepl/pull/58),
  [`67546c6`](https://github.com/midodimori/langrepl/commit/67546c62cb6b053c4990d3e645517282e0c8d35e))


## v1.8.1 (2025-11-29)

### Chores

- Improve skills instructions
  ([`c26b054`](https://github.com/midodimori/langrepl/commit/c26b054f9e829cf0afbe647aba13d60f912389d1))


## v1.8.0 (2025-11-29)

### Features

- Add Anthropic skill system (#57) ([#57](https://github.com/midodimori/langrepl/pull/57),
  [`6c85a0a`](https://github.com/midodimori/langrepl/commit/6c85a0aff5c8af8a24c52814a5768c3032f6e236))


## v1.7.4 (2025-11-26)

### Bug Fixes

- Add repair json (#56) ([#56](https://github.com/midodimori/langrepl/pull/56),
  [`6fa1cee`](https://github.com/midodimori/langrepl/commit/6fa1ceec1d4b9739974f6fe17d058939901b0ec2))


## v1.7.3 (2025-11-26)

### Bug Fixes

- Handle JSON string serialization in tool parameters (#55)
  ([#55](https://github.com/midodimori/langrepl/pull/55),
  [`4d3de33`](https://github.com/midodimori/langrepl/commit/4d3de3331a4ad05ce6683b152c58a6c2499d56cc))


## v1.7.2 (2025-11-25)

### Chores

- Add version warning
  ([`91c621e`](https://github.com/midodimori/langrepl/commit/91c621e3592704db93ba0fb36a23d88746997403))


## v1.7.1 (2025-11-25)

### Chores

- Add version and feature notes
  ([`ff31f6d`](https://github.com/midodimori/langrepl/commit/ff31f6d249c21c7f426761bd5e8ab2aea55e538e))


## v1.7.0 (2025-11-25)

### Features

- Add config versioning with automatic migration (#53)
  ([#53](https://github.com/midodimori/langrepl/pull/53),
  [`a1d7159`](https://github.com/midodimori/langrepl/commit/a1d715926fa97bc527b4bd1d653897ab28afd2d8))

- Implement tool catalog system with config schema v2 (#54)
  ([#54](https://github.com/midodimori/langrepl/pull/54),
  [`98b835f`](https://github.com/midodimori/langrepl/commit/98b835ffac216050472a25c03f09b747d01f4e6c))


## v1.6.5 (2025-11-21)

### Bug Fixes

- Configure PSR for incremental changelog updates
  ([`cf88659`](https://github.com/midodimori/langrepl/commit/cf88659a43b95fd1371ccb99854b59617b876735))

- Handle None values and skip empty diffs in approval rendering
  ([`be58af9`](https://github.com/midodimori/langrepl/commit/be58af98ac50dd371e740edea2499e129031019c))

- Improve renderer indentation and HTML preservation (#52)
  ([#52](https://github.com/midodimori/langrepl/pull/52),
  [`c327848`](https://github.com/midodimori/langrepl/commit/c32784893e6617652c1c5c494765123cf1c1e1be))

- Use prompt_toolkit event loop to prevent input freeze after idle
  ([`ae8ec90`](https://github.com/midodimori/langrepl/commit/ae8ec902e04380293ca164695ed092753cac2128))

### Chores

- Add gemini 3
  ([`a060d6a`](https://github.com/midodimori/langrepl/commit/a060d6a6689f092dfc24511772c5548b0b8d0545))

- Suppress langsmith warning
  ([`04fee7f`](https://github.com/midodimori/langrepl/commit/04fee7f14a9dc7104622f09b5845ab2583cc6505))

- Sync deps
  ([`0eabe29`](https://github.com/midodimori/langrepl/commit/0eabe294c9ae60a4af48226cf8e7f6fdf50ab00b))

### Continuous Integration

- Simplify release workflow with PSR CLI
  ([`c83b40e`](https://github.com/midodimori/langrepl/commit/c83b40e0bf20fd4c5e26cb6ba8f716b07d93942d))

- Simplify workflow, PSR handles uv.lock automatically
  ([`bff83cc`](https://github.com/midodimori/langrepl/commit/bff83cc1648f64fa429afabd2abf986cf82e0309))

- Skip CI on release commits and fix PSR changelog config
  ([`afab928`](https://github.com/midodimori/langrepl/commit/afab928cd21e2161aa30fdce84940163234b3feb))

- Use PAT to trigger publish workflow and sync uv.lock
  ([`c3ba0ca`](https://github.com/midodimori/langrepl/commit/c3ba0ca4e39a72515208607217123239334c1e9e))


## v1.6.4 (2025-11-21)

### Bug Fixes

- Improve renderer indentation and HTML preservation ([#52](https://github.com/midodimori/langrepl/pull/52),
  [`c327848`](https://github.com/midodimori/langrepl/commit/c327848a0f8e7964f4e2f7be47e3e0f1deb5de95))

### Continuous Integration

- Simplify workflow, PSR handles uv.lock automatically
  ([`bff83cc`](https://github.com/midodimori/langrepl/commit/bff83cc1648f64fa429afabd2abf986cf82e0309))


## v1.6.3 (2025-11-20)

### Bug Fixes

- Handle None values and skip empty diffs in approval rendering
  ([`be58af9`](https://github.com/midodimori/langrepl/commit/be58af9edb936b4fc6a12e09f6bbf3ac5b1f8b21))

### Continuous Integration

- Simplify release workflow with PSR CLI
  ([`c83b40e`](https://github.com/midodimori/langrepl/commit/c83b40e97adc7b929be60daea0056b00df92af4d))

- Use PAT to trigger publish workflow and sync uv.lock
  ([`c3ba0ca`](https://github.com/midodimori/langrepl/commit/c3ba0ca2e3e7afb61bfa9d7a603a8ac50bc95ca5))


## v1.6.2 (2025-11-19)

### Continuous Integration

- Fix release
  ([`d3d38bb`](https://github.com/midodimori/langrepl/commit/d3d38bb6da37a02444c4150a78fa112eb0bc7008))

- Remove release please, use manual verion bump
  ([`c65060e`](https://github.com/midodimori/langrepl/commit/c65060e952c7199f6c44153cc8a2d077e3666f22))

### Features

- Add bash mode ([#51](https://github.com/midodimori/langrepl/pull/51),
  [`9dc9514`](https://github.com/midodimori/langrepl/commit/9dc951480a3af55d911e6cc65b5b7b69f15c22d2))

* feat: add bash mode for direct command execution

Toggle with Ctrl-B to execute shell commands directly without agent interaction. Bash mode indicator
  shows in toolbar (danger color). Commands run in working directory with stdout/stderr display.

* feat: add /hotkeys command and Ctrl-K shortcut

Add /hotkeys command to display keyboard shortcuts in a formatted table. Ctrl-K triggers the
  command. Hotkeys are dynamically registered and formatted from key bindings.

---------

Co-authored-by: midodimori <midodimori@users.noreply.github.com>


## v1.6.1 (2025-11-19)

### Bug Fixes

- Release please token
  ([`3891a14`](https://github.com/midodimori/langrepl/commit/3891a1426b85326c90d8113165e5efe4684621f6))

### Chores

- **main**: Release 1.6.1 ([#50](https://github.com/midodimori/langrepl/pull/50),
  [`06235ab`](https://github.com/midodimori/langrepl/commit/06235ab1e425af1de61ea82c0c5ec6d145a14151))

* chore(main): release 1.6.1

* chore: update uv.lock after version bump

---------

Co-authored-by: github-actions[bot] <github-actions[bot]@users.noreply.github.com>


## v1.6.0 (2025-11-19)

### Bug Fixes

- Disable attestations for TestPyPI to avoid conflicts
  ([`abcfcd2`](https://github.com/midodimori/langrepl/commit/abcfcd2b6297a35bfc4c3e8f74c4892254afba58))

- Skip TestPyPI if version already exists
  ([`a448c49`](https://github.com/midodimori/langrepl/commit/a448c4961b79b1d3b2cfbdb0ea6e97b0cedcddca))

### Chores

- Add workflow_dispatch trigger to publish workflow
  ([`2803117`](https://github.com/midodimori/langrepl/commit/28031170613c828926fc09bd2a5d082858ed045d))

- **main**: Release 1.6.0 ([#48](https://github.com/midodimori/langrepl/pull/48),
  [`747205d`](https://github.com/midodimori/langrepl/commit/747205d00907aac3efd59cdd47303c37c5735336))

### Features

- Add message indexing for resume/replay performance
  ([#49](https://github.com/midodimori/langrepl/pull/49),
  [`1a06163`](https://github.com/midodimori/langrepl/commit/1a061633bcd142038a2483ad567f8b11148b584e))

Implements BaseCheckpointer with indexed message lookups: - IndexedAsyncSqliteSaver: automatic
  message indexing with lazy initialization - MemoryCheckpointer: singleton pattern with equivalent
  interface - Fast path: O(1) indexed queries vs O(n) checkpoint traversal - Handlers refactored to
  use new get_human_messages() API

Co-authored-by: midodimori <midodimori@users.noreply.github.com>


## v1.5.0 (2025-11-17)

### Chores

- Add spacing below error for consistency
  ([`0b7bc35`](https://github.com/midodimori/langrepl/commit/0b7bc354e2d7cd117f069c121761af3b837d9d81))

- Update release-please
  ([`3ea9c72`](https://github.com/midodimori/langrepl/commit/3ea9c72fdae8ab8ffc8d0a661f2c9d2bedb9438a))

- Update uv.lock
  ([`b0550b4`](https://github.com/midodimori/langrepl/commit/b0550b43ed8545097e576e9079db0f598157ef89))

- **main**: Release 1.5.0 ([#47](https://github.com/midodimori/langrepl/pull/47),
  [`5ea490d`](https://github.com/midodimori/langrepl/commit/5ea490d151e7df96366a72e6df83cb6381e25ab6))

* chore(main): release 1.5.0

* chore: update uv.lock after version bump

---------

Co-authored-by: github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>

Co-authored-by: github-actions[bot] <github-actions[bot]@users.noreply.github.com>

### Features

- Add streaming ([#46](https://github.com/midodimori/langrepl/pull/46),
  [`b94daf8`](https://github.com/midodimori/langrepl/commit/b94daf8c54cdcff0ff1d1b388ddf25511911021a))

* feat: implement token-by-token streaming with preview display

- Change stream mode from 'updates' to ['messages', 'updates'] for dual-mode streaming - Add
  streaming preview showing last 3 lines of response while generating - Implement streaming state
  tracking (active, message_id, text_buffer, chunks) - Merge chunks into final AIMessage when
  streaming completes - Only render AI and Tool messages (skip Human messages) - Change streaming
  default from False to True in LLMConfig - Update tests to handle 3-tuple chunk format (namespace,
  mode, data)

* feat: add streaming support for ZhipuAI wrapper

- Implement _stream and _astream methods for token-by-token streaming - Extract reasoning_content
  from deltas and format as thinking blocks - Strip leading newlines from content and reasoning text
  - Properly inject thinking config into streaming requests

* refactor: improve prefix rendering with segment-based approach

- Refactor PrefixedMarkdown to use segment-based rendering instead of line-splitting - Render
  markdown first, then insert prefix before first non-empty segment - More robust handling of
  complex markdown structures

* chore: add gemini thinking model

---------

Co-authored-by: midodimori <midodimori@users.noreply.github.com>


## v1.4.1 (2025-11-15)

### Bug Fixes

- Wrap Path.glob() in asyncio.to_thread() to prevent BlockingError in server mode
  ([`9a4f7ee`](https://github.com/midodimori/langrepl/commit/9a4f7ee766d1a122dfa5096c112e4d37c2788394))

### Chores

- Add PyPi ([#45](https://github.com/midodimori/langrepl/pull/45),
  [`7f2c1a1`](https://github.com/midodimori/langrepl/commit/7f2c1a1375bbc4d9018c3a2e3b4115897039e2d8))

Co-authored-by: midodimori <midodimori@users.noreply.github.com>

- Move langraph cli to main dependencies
  ([`da75997`](https://github.com/midodimori/langrepl/commit/da75997eb26f8a4b61d5cb8df4dfbe8bd528f041))

- **main**: Release 1.4.1 ([#44](https://github.com/midodimori/langrepl/pull/44),
  [`95d960a`](https://github.com/midodimori/langrepl/commit/95d960a98b8f7f15136394d0993c794d21d3d6e7))

Co-authored-by: github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>

Co-authored-by: midodimori <44535548+midodimori@users.noreply.github.com>

### Documentation

- Update
  ([`af8607d`](https://github.com/midodimori/langrepl/commit/af8607d00ed4b181e397d905c719490120d8d878))

### Refactoring

- Add directory-based config structure with backward compatibility
  ([#41](https://github.com/midodimori/langrepl/pull/41),
  [`2e15373`](https://github.com/midodimori/langrepl/commit/2e1537320eea9050d22bbff4fd6113b0d19de69e))

Support both directory-based (agents/, llms/) and single-file (config.agents.yml) formats. All
  existing configs continue to work.

Co-authored-by: midodimori <midodimori@users.noreply.github.com>


## v1.4.0 (2025-11-11)

### Chores

- **main**: Release 1.4.0 ([#39](https://github.com/midodimori/langrepl/pull/39),
  [`05010c8`](https://github.com/midodimori/langrepl/commit/05010c8e6429a7989b32f35b7d88509042668986))

Co-authored-by: github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>

### Documentation

- Update
  ([`4f83edb`](https://github.com/midodimori/langrepl/commit/4f83edb8422f0a05d3ef279b8f63ada83d8097bb))

### Features

- Add one-shot mode ([#40](https://github.com/midodimori/langrepl/pull/40),
  [`43cb1de`](https://github.com/midodimori/langrepl/commit/43cb1de82de32a2c7c6ac6642f6c3a9d2ef4b44c))

* feat: add one-shot mode

* refactor: remove unnecessary timestamp sorting

* feat: support one-shot mode with server

- Add _get_or_create_thread() and _send_message() - Support -r flag to resume last thread - Server
  stays running after message sent

---------

Co-authored-by: midodimori <midodimori@users.noreply.github.com>


## v1.3.0 (2025-11-10)

### Chores

- **main**: Release 1.3.0 ([#36](https://github.com/midodimori/langrepl/pull/36),
  [`fe92afe`](https://github.com/midodimori/langrepl/commit/fe92afe3dd66b709089a4c717c2e0c8254b72855))

Co-authored-by: github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>

### Documentation

- Update demo
  ([`799001d`](https://github.com/midodimori/langrepl/commit/799001dfe87a64e617ce09bec17cf3d4fc21e512))

### Features

- Add multimodal image support with builder pattern
  ([#37](https://github.com/midodimori/langrepl/pull/37),
  [`dc3a94f`](https://github.com/midodimori/langrepl/commit/dc3a94fbe4d0ac6ce101b813775e2ecebac79071))

* feat: add multimodal image support with builder pattern

- Add ImageResolver for @:image: references and absolute paths - Add clipboard paste support for
  images - Implement MessageContentBuilder to separate content construction from UI - Add base64
  encoding utility for image files - Remove resolve_refs from completers (moved to builder) - Add
  async interface to SlashCommandCompleter - Fix file path detection to distinguish from slash
  commands

* docs: add multimodal image support to features

* fix: correct git and fd command syntax in image resolver

Git ls-files requires glob patterns (*.png), not -e flags. fd requires -e flags without leading dots
  (-e png, not -e .png). Previously git command always failed and fd worked by accident.

* refactor: use mock_session fixture to eliminate duplication

* refactor: catch specific exceptions in base64 decode test

* refactor: improve error handling for image resolution

* refactor: defer image validation to submit time

- Allow all images in tab completion and path resolution - Validate formats only in
  build_content_block to prevent unsupported images from entering conversation history - Remove sort
  -u from file resolver for faster tab completion - Add is_image_file() for MIME-based detection

---------

Co-authored-by: midodimori <midodimori@users.noreply.github.com>

### Refactoring

- Include untracked files in file completion ([#38](https://github.com/midodimori/langrepl/pull/38),
  [`67b2321`](https://github.com/midodimori/langrepl/commit/67b2321d8de04e48d580864416fa3a0f8e915f02))


## v1.2.1 (2025-11-09)

### Bug Fixes

- Add short content for task tool result
  ([`2e094ad`](https://github.com/midodimori/langrepl/commit/2e094ad9f6ea22e763d3847cfcc72f1eb4cc554a))

- Always return short_content in task tool
  ([`bc1200d`](https://github.com/midodimori/langrepl/commit/bc1200da099a0c415f78b32b48bfa6970e96aad6))

### Chores

- Update notes for agents
  ([`09cc248`](https://github.com/midodimori/langrepl/commit/09cc2487ac7eea27aa95c0d2724e7c5d70146e25))

- **main**: Release 1.2.1 ([#35](https://github.com/midodimori/langrepl/pull/35),
  [`61023bd`](https://github.com/midodimori/langrepl/commit/61023bdac75fa5663882dae9e66b0e533c80cead))

Co-authored-by: github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>


## v1.2.0 (2025-11-09)

### Chores

- **main**: Release 1.2.0 ([#34](https://github.com/midodimori/langrepl/pull/34),
  [`d502ef1`](https://github.com/midodimori/langrepl/commit/d502ef1649e4901629e6d0d459221ab708a326ed))

Co-authored-by: github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>

### Features

- Add model indicators in /model selector
  ([`3dbe31f`](https://github.com/midodimori/langrepl/commit/3dbe31f8a5d65b9a65bfeeae080df08f6b90b6ae))

- Show [current] and [default] indicators with distinct colors - Display context model (from -m
  flag) in agent list - Include all models in selector (not just non-current) - Use info_color for
  [current] and accent_color for [default]


## v1.1.3 (2025-11-09)

### Bug Fixes

- Add cache for approval to prevent duplication
  ([`b99f972`](https://github.com/midodimori/langrepl/commit/b99f9721ecac55e6c6907767475b6811ad7985dc))

### Chores

- **main**: Release 1.1.3 ([#33](https://github.com/midodimori/langrepl/pull/33),
  [`40e9262`](https://github.com/midodimori/langrepl/commit/40e92628f0bfc9ff7f80fce4c3b90c998ea828e1))

Co-authored-by: github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>


## v1.1.2 (2025-11-09)

### Bug Fixes

- Restore stable state by reverting recent changes
  ([`121d003`](https://github.com/midodimori/langrepl/commit/121d003dffc8e9574a8ac86189580856fd8368a6))

### Chores

- **main**: Release 1.1.2 ([#32](https://github.com/midodimori/langrepl/pull/32),
  [`23f7f74`](https://github.com/midodimori/langrepl/commit/23f7f743da062d30ae4480c1c0666261d1709798))

Co-authored-by: github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>


## v1.1.1 (2025-11-09)

### Bug Fixes

- Tool call/result pairing in live and resume modes
  ([#30](https://github.com/midodimori/langrepl/pull/30),
  [`3e5059a`](https://github.com/midodimori/langrepl/commit/3e5059a7b135e76f570800cd5a0e1ee9998f479c))

- Remove tool call rendering from interrupt approval prompts - Buffer tool calls and render when
  ToolMessage arrives - Ensures tool calls pair with their results in all scenarios

Co-authored-by: midodimori <midodimori@users.noreply.github.com>

### Chores

- **main**: Release 1.1.1 ([#31](https://github.com/midodimori/langrepl/pull/31),
  [`269090a`](https://github.com/midodimori/langrepl/commit/269090acea6a8fad107317992945b06b217fb21e))

Co-authored-by: github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>


## v1.1.0 (2025-11-08)

### Bug Fixes

- Handle multiple pending interrupts ([#28](https://github.com/midodimori/langrepl/pull/28),
  [`9cc140f`](https://github.com/midodimori/langrepl/commit/9cc140f629203596441d183329912c11b7f8f3e3))

- Always map resume values to interrupt ID format - Support multiple interrupts in handler - Remove
  extra spacing between tool calls

Co-authored-by: midodimori <midodimori@users.noreply.github.com>

### Chores

- **main**: Release 1.1.0 ([#26](https://github.com/midodimori/langrepl/pull/26),
  [`155d473`](https://github.com/midodimori/langrepl/commit/155d473968cfb1622b3b79433ee3e4adb163d00d))

Co-authored-by: github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>

### Features

- Add ctrl c key binding for stream cancellation
  ([#27](https://github.com/midodimori/langrepl/pull/27),
  [`4e527af`](https://github.com/midodimori/langrepl/commit/4e527af6311c14ad2dc93b92b41230d06a00178f))

* feat: add ctrl c key binding for stream cancellation

* docs: fix minor typo in graph factory

---------

Co-authored-by: midodimori <midodimori@users.noreply.github.com>

- Improve message rendering with visual indicators and formatting
  ([#25](https://github.com/midodimori/langrepl/pull/25),
  [`b88cfdf`](https://github.com/midodimori/langrepl/commit/b88cfdfb0e3304167f6a1dd75058ef6b942bf4dc))

- Add visual indicators (⚙ for tools, ◆︎ for AI responses) - Improve tool call formatting with
  vertical layout for arguments - Skip rendering empty tool messages - Update theme to use
  "indicator" style instead of "tool" - Generate unique IDs for tool messages

Co-authored-by: midodimori <midodimori@users.noreply.github.com>

- Pair tool calls with results in rendering ([#29](https://github.com/midodimori/langrepl/pull/29),
  [`e2fc941`](https://github.com/midodimori/langrepl/commit/e2fc94104a4dd7b7714f3720e6075d13774452a1))

- Buffer tool calls and render with corresponding results - Add position/total count (1/2) for
  multiple tools - Make Renderer stateful with pending_tool_calls tracking - Update tests to use
  renderer fixture

Co-authored-by: midodimori <midodimori@users.noreply.github.com>


## v1.0.2 (2025-11-07)

### Bug Fixes

- Input tokens count
  ([`822f45c`](https://github.com/midodimori/langrepl/commit/822f45ce13a60fe3b751c74eb6cd0098ae2382f4))

### Chores

- **main**: Release 1.0.2 ([#24](https://github.com/midodimori/langrepl/pull/24),
  [`797adde`](https://github.com/midodimori/langrepl/commit/797adde38794842b3d090be2222acc083fc3a12f))

Co-authored-by: github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>


## v1.0.1 (2025-11-07)

### Bug Fixes

- Render interrupt
  ([`ae07b44`](https://github.com/midodimori/langrepl/commit/ae07b44fc660b53540deb0a41289325da2aca032))

### Chores

- **main**: Release 1.0.1 ([#23](https://github.com/midodimori/langrepl/pull/23),
  [`017244f`](https://github.com/midodimori/langrepl/commit/017244f61e463f8006973332a8b24e3fbd03e1de))

Co-authored-by: github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>

### Refactoring

- Consolidate tool message creation into shared utility
  ([`4cca220`](https://github.com/midodimori/langrepl/commit/4cca220f87ee5947d3a13855b880eceeef356bfa))

- Extract create_tool_message() utility in src/utils/render.py - Refactor
  src/tools/subagents/task.py to use new utility - Refactor src/middleware/approval.py to use new
  utility


## v1.0.0 (2025-11-07)

### Bug Fixes

- Correct ToolRuntime context type and auto-approve internal tools
  ([`8d17619`](https://github.com/midodimori/langrepl/commit/8d176190a4499dd3d66b74d56fda8643154ef623))

### Chores

- **main**: Release 1.0.0 ([#22](https://github.com/midodimori/langrepl/pull/22),
  [`5d85cff`](https://github.com/midodimori/langrepl/commit/5d85cfffc761e2d74946c6d390c3a7038582298b))

Co-authored-by: github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>

### Features

- Migrate to LangChain v1.0 with context-based architecture
  ([#20](https://github.com/midodimori/langrepl/pull/20),
  [`d003cce`](https://github.com/midodimori/langrepl/commit/d003cce49694ce0140249386db96b655dbe58fa0))

BREAKING CHANGE: Major upgrade from LangChain 0.x to 1.x with architectural changes

## Dependencies - Upgrade all langchain packages from 0.x to 1.x - Upgrade langgraph from 0.5.2 to
  1.0.2 - Upgrade langgraph-checkpoint-sqlite from 2.0.10 to 3.0.0 - Upgrade supporting packages
  (rich, pydantic, pytest, etc.)

## Architecture Changes - Replace BaseState with AgentState + AgentContext separation - Move from
  config_schema to context_schema pattern - Refactor prompt handling from SystemMessage to string -
  Introduce AgentContext for runtime configuration - Separate concerns between graph state and
  execution context

## Code Organization - Move approval middleware from tools/wrapper.py to middleware/approval.py -
  Restructure state management (state/base.py → agents/state.py) - Add new agents/context.py for
  AgentContext - Reorganize tool implementations under tools/impl/ - Create dedicated middleware
  layer

## API Changes - Graph.astream() now accepts context parameter instead of embedding in config - Tool
  approval configuration moved to tool.metadata - Prompts are now plain strings instead of
  SystemMessage objects - Context tracking moved from messages to dedicated middleware - Token/cost
  updates now flow through middleware layer

## Test Updates - Rename test_base_state.py to test_agent_state.py - Add tests for new reducers
  (add_reducer, sum_reducer) - Update all tests for new context/state patterns - Fix imports across
  test suite

Co-authored-by: midodimori <midodimori@users.noreply.github.com>

### BREAKING CHANGES

- Major upgrade from LangChain 0.x to 1.x with architectural changes


## v0.3.1 (2025-11-05)

### Bug Fixes

- Trigger release for refactor changes
  ([`24ab34f`](https://github.com/midodimori/langrepl/commit/24ab34ff49c7309ea341a90decdbb85d81f68dfe))

### Chores

- Setup Release Please for automated releases
  ([#17](https://github.com/midodimori/langrepl/pull/17),
  [`f83fa1f`](https://github.com/midodimori/langrepl/commit/f83fa1fa20911160f504fa43b0badb68ce0083a9))

- Add Release Please GitHub Action workflow - Create CHANGELOG.md with historical releases (v0.1.0 -
  v0.3.0) - Remove old label-based version bump workflow - Remove bump-my-version dependency and
  configuration

Co-authored-by: midodimori <midodimori@users.noreply.github.com>

- **main**: Release 0.3.1 ([#19](https://github.com/midodimori/langrepl/pull/19),
  [`098c27e`](https://github.com/midodimori/langrepl/commit/098c27e39e22a6678647bddc185b2f05783de8ef))

Co-authored-by: github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>

### Refactoring

- **cli**: Reorganize bootstrap layer and expand tests
  ([#18](https://github.com/midodimori/langrepl/pull/18),
  [`7ede2de`](https://github.com/midodimori/langrepl/commit/7ede2de6f83cf101df18ab1141b3831ee056c75d))

* refactor(cli): reorganize bootstrap layer and expand tests

- move CLI entry point under src.cli.bootstrap and update entry scripts - split interface modules
  into bootstrap, dispatchers, handlers, resolvers, and ui packages - make initializer directory
  setup async-safe and tweak resume handling - drop the unused cli.multiline_threshold setting - add
  extensive fixtures and tests covering the restructured CLI components

* fix: update ci.yml with fd package

* docs: Update prerequisites links

* test: cleanup and improve test assertions

- Remove unused imports and parameters - Add missing mock patches for console output verification -
  Fix async iterator mock in completer fixture

---------

Co-authored-by: midodimori <midodimori@users.noreply.github.com>


## v0.3.0 (2025-11-02)

### Bug Fixes

- Handle directory paths with spaces in completion
  ([`b604cae`](https://github.com/midodimori/langrepl/commit/b604cae770886134d6a27fa62e510c9798ce17f8))

- Use null-delimited output (-z, -0) in git and fd commands - Prevents path splitting on whitespace
  in directory names

### Chores

- Update docstring for filesystem
  ([`5fa3b12`](https://github.com/midodimori/langrepl/commit/5fa3b123ab9ec2bc1a6ff1362647dae1f148e96b))

- Uv.lock
  ([`3fe027e`](https://github.com/midodimori/langrepl/commit/3fe027e1e6c9ea20092411969150298380505dec))

### Features

- Add @ reference completion for file paths
  ([`3dd5ef0`](https://github.com/midodimori/langrepl/commit/3dd5ef0c82d759492b768641b16ca1fabd8c88e9))

- Type @ to autocomplete file paths from project - Tab/Enter to select and insert file references -
  References preserved when replaying conversations - Security improvements for file path handling

### Performance Improvements

- Optimize directory set lookups in completion
  ([`ccb6ea0`](https://github.com/midodimori/langrepl/commit/ccb6ea08da967a90ff9ba2b5142a5c90a1b815ac))

- Create directory_set once instead of recreating in sort_key - Use set for O(1) lookups instead of
  O(n) list checks


## v0.2.4 (2025-10-31)

### Bug Fixes

- Address code review feedback and security warnings
  ([`be53157`](https://github.com/midodimori/langrepl/commit/be53157cb5771dc3a633353bf5a0cf93603b5e98))

- Fix renderer status check bug: use None as default instead of 'error' - Replace identity
  comprehension with list() constructor - Add error handling for checkpoint deletion failures -
  Batch checkpoint deletion with WHERE IN clause for performance - Add error message sanitization
  for non-safe exceptions - Add nosec annotation for false positive SQL injection warning

- Improve tool error handling and update for LangGraph v2 compatibility
  ([`42a8cf6`](https://github.com/midodimori/langrepl/commit/42a8cf6f3084c2cc891f6981a1a39eb15341d766))

- Add custom error formatter to extract clean error messages from ToolException - Update
  CompressingToolNode to use tool_runtime.config (LangGraph v2 API) - Let ToolException bubble up
  through wrapper for proper ToolNode handling - Update renderer to check status field for error
  detection - Add handle_tool_errors to ToolNode in tests

- Properly rewind conversation thread by deleting checkpoints after replay point
  ([`24b419f`](https://github.com/midodimori/langrepl/commit/24b419f0cf8ea8af1fc7c6bb6505e5fb23c04db6))

- Add delete_checkpoints_after utility to remove all checkpoints after a selected checkpoint -
  Replace checkpoint forking approach with direct checkpoint deletion in replay handler - Remove
  replay_checkpoint_id session field as it's no longer needed - Simplify checkpoint factory
  docstring and remove unused logger - Improve replay message tracking to only update on new
  messages

### Refactoring

- Standardize key bindings to use Keys enum constants
  ([`6121be4`](https://github.com/midodimori/langrepl/commit/6121be4a7654fead66f3cd23e85ab3b20d07bb8d))

- Replace string literals ("c-c", "s-tab") with Keys enum (ControlC, BackTab) - Fix incorrect
  docstring: Ctrl-J instead of Shift+Enter


## v0.2.3 (2025-10-29)

### Bug Fixes

- Allow dirty working directory in version bump workflow
  ([`d48cfd0`](https://github.com/midodimori/langrepl/commit/d48cfd0d38d339be2145b59c28a812a30ed4f660))

- Add --allow-dirty flag to bump-my-version command - Prevents failure when uv.lock is modified
  during workflow

### Chores

- Uv.lock
  ([`1ad5e5b`](https://github.com/midodimori/langrepl/commit/1ad5e5bb8eacc9e321facf9bed77a61edd40c961))

### Continuous Integration

- Install ripgrep and tree
  ([`ffe519a`](https://github.com/midodimori/langrepl/commit/ffe519a77229b8d65a29d4e421b57e16fdff6d10))

### Testing

- Add integration tests for tools
  ([`68e29b5`](https://github.com/midodimori/langrepl/commit/68e29b5b0b2026d6d07bc7c17778db741c86ee57))


## v0.2.2 (2025-10-29)

### Refactoring

- Extract helper function for attribute access
  ([`c76d1db`](https://github.com/midodimori/langrepl/commit/c76d1dbaff0ebf39d27e975db9f73b96be20fde3))

- Add _get_attr helper to handle dict/model attribute extraction - Simplifies _render_diff_args
  logic - Improves readability and reduces duplication

- Flatten tool parameters to fix API compatibility
  ([`87d884d`](https://github.com/midodimori/langrepl/commit/87d884da6462b00584d56e286341e05c3b5df789))

- Remove wrapper Input models (EditFileInput, etc) - Use direct list parameters for edits and moves
  - Fix type hints in render function - Remove unused args_schema parameter


## v0.2.1 (2025-10-29)

### Bug Fixes

- Add missing injected params to EditMemoryFileInput
  ([`73f768c`](https://github.com/midodimori/langrepl/commit/73f768cfdf8b9fabd1a55b9838505bff5b664223))


## v0.2.0 (2025-10-29)

### Bug Fixes

- Add TTY check before ANSI escape codes
  ([`585e39d`](https://github.com/midodimori/langrepl/commit/585e39d60307ed0cce2e0ab7fd36c375cedd5ec9))

Prevent issues when output is redirected or terminal doesn't support ANSI.

### Features

- Add model switching for subagents
  ([`8da512a`](https://github.com/midodimori/langrepl/commit/8da512acf7e7f1fcc2715623246546260eba0b32))

Extend /model command to support switching models for both agents and subagents. Shows unified
  selection list with current agent and its subagents.

- Add load_subagents_config() and update_subagent_llm() to Initializer - Refactor ModelHandler to
  show single unified agent/subagent list - Display format: [Agent] name (model) or [Subagent] name
  (model) - Update aiohttp dependency to 3.13.2

- Clean
  ([`70898f9`](https://github.com/midodimori/langrepl/commit/70898f91cd813fd01c780ecd85177c60ad6a563d))


## v0.1.1 (2025-10-28)

### Bug Fixes

- Add write permissions to version bump workflow
  ([`0700c76`](https://github.com/midodimori/langrepl/commit/0700c76abc813daa83680d6fa2df5a15d683d71a))

- Env example
  ([`b2c24ca`](https://github.com/midodimori/langrepl/commit/b2c24ca65ac6a2e21e8e2503c4e55ae0d117a726))

### Chores

- Restructure README
  ([`fd3c13c`](https://github.com/midodimori/langrepl/commit/fd3c13c3cb87beaa797790f6d7e41563c0672580))

- Update README
  ([`0123591`](https://github.com/midodimori/langrepl/commit/0123591bdb5cabb0e2a76b689b64ce047f42e2c4))

- Workflow
  ([`062b9db`](https://github.com/midodimori/langrepl/commit/062b9db3a45de2a7e939e9fc4280b0dd34b2cb0a))

### Features

- Add config and tool_call_id to EditFileInput ([#4](https://github.com/midodimori/langrepl/pull/4),
  [`e1e250f`](https://github.com/midodimori/langrepl/commit/e1e250f52164234bfee3a59a1f63f6136753e398))

- Add repair command for MCP before retrying
  ([`9f7cdd2`](https://github.com/midodimori/langrepl/commit/9f7cdd27ae4a2df7614394a6428c430441a50bb4))

- Add support for zhipuai glm
  ([`88815a5`](https://github.com/midodimori/langrepl/commit/88815a5a95a1fff46909c14fb29a393ea4bdecc8))

- Automate version bumping via GitHub Actions
  ([`b55e511`](https://github.com/midodimori/langrepl/commit/b55e511bb58f6bfd7ad5d8ce32375bc3d89fc05f))

- Improve agent switching with model sync and default persistence
  ([#5](https://github.com/midodimori/langrepl/pull/5),
  [`33dd143`](https://github.com/midodimori/langrepl/commit/33dd143c76de3fe43c55effb96751c5bcb1d99e7))

Changes: - Agent switching now updates model to match the selected agent's config - Switched agent
  is automatically marked as default for future sessions - Improved type safety by making agent and
  model non-nullable in Context - Removed unnecessary None checks and simplified code throughout

Implementation: - Added BatchAgentConfig.update_default_agent() to persist default agent -
  AgentHandler now loads selected agent's config and syncs model - Simplified Context type
  annotations (str | None -> str) - Cleaned up unnecessary getattr() calls in favor of direct
  attribute access

Co-authored-by: midodimori <midodimori@users.noreply.github.com>

- Setup workflow
  ([`9cf1738`](https://github.com/midodimori/langrepl/commit/9cf17386f4d898adb14972c66c3c0112c6f5adc8))
