Directory structure:
└── langchain-ai-deepagents/
├── README.md
├── examples/
│   └── research/
│       └── research_agent.py
└── src/
└── deepagents/
├── graph.py
├── middleware.py
├── model.py
├── prompts.py
├── state.py
├── tools.py
└── types.py


Files Content:

================================================
FILE: README.md
================================================
# 🧠🤖Deep Agents

Using an LLM to call tools in a loop is the simplest form of an agent.
This architecture, however, can yield agents that are “shallow” and fail to plan and act over longer, more complex tasks.
Applications like “Deep Research”, "Manus", and “Claude Code” have gotten around this limitation by implementing a combination of four things:
a **planning tool**, **sub agents**, access to a **file system**, and a **detailed prompt**.

<img src="deep_agents.png" alt="deep agent" width="600"/>

`deepagents` is a Python package that implements these in a general purpose way so that you can easily create a Deep Agent for your application.

**Acknowledgements: This project was primarily inspired by Claude Code, and initially was largely an attempt to see what made Claude Code general purpose, and make it even more so.**

## Installation

```bash
pip install deepagents
```

## Usage

(To run the example below, will need to `pip install tavily-python`)

```python
import os
from typing import Literal
from tavily import TavilyClient
from deepagents import create_deep_agent

tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

# Search tool to use to do research
def internet_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = False,
):
    """Run a web search"""
    return tavily_client.search(
        query,
        max_results=max_results,
        include_raw_content=include_raw_content,
        topic=topic,
    )


# Prompt prefix to steer the agent to be an expert researcher
research_instructions = """You are an expert researcher. Your job is to conduct thorough research, and then write a polished report.

You have access to a few tools.

## `internet_search`

Use this to run an internet search for a given query. You can specify the number of results, the topic, and whether raw content should be included.
"""

# Create the agent
agent = create_deep_agent(
    [internet_search],
    research_instructions,
)

# Invoke the agent
result = agent.invoke({"messages": [{"role": "user", "content": "what is langgraph?"}]})
```

See [examples/research/research_agent.py](examples/research/research_agent.py) for a more complex example.

The agent created with `create_deep_agent` is just a LangGraph graph - so you can interact with it (streaming, human-in-the-loop, memory, studio)
in the same way you would any LangGraph agent.

## Creating a custom deep agent

There are several parameters you can pass to `create_deep_agent` to create your own custom deep agent.

### `tools` (Required)

The first argument to `create_deep_agent` is `tools`.
This should be a list of functions or LangChain `@tool` objects.
The agent (and any subagents) will have access to these tools.

### `instructions` (Required)

The second argument to `create_deep_agent` is `instructions`.
This will serve as part of the prompt of the deep agent.
Note that our deep agent middleware appends further instructions to the deep agent regarding to-do list, filesystem, and subagent usage, so this is not the *entire* prompt the agent will see.

### `subagents` (Optional)

A keyword-only argument to `create_deep_agent` is `subagents`.
This can be used to specify any custom subagents this deep agent will have access to.
You can read more about why you would want to use subagents [here](#sub-agents)

`subagents` should be a list of dictionaries, where each dictionary follow this schema:

```python
class SubAgent(TypedDict):
    name: str
    description: str
    prompt: str
    tools: NotRequired[list[str]]
    model: NotRequired[Union[LanguageModelLike, dict[str, Any]]]
    middleware: NotRequired[list[AgentMiddleware]]

class CustomSubAgent(TypedDict):
    name: str
    description: str
    graph: Runnable
```

**SubAgent fields:**
- **name**: This is the name of the subagent, and how the main agent will call the subagent
- **description**: This is the description of the subagent that is shown to the main agent
- **prompt**: This is the prompt used for the subagent
- **tools**: This is the list of tools that the subagent has access to. By default will have access to all tools passed in, as well as all built-in tools.
- **model**: Optional model instance OR dictionary for per-subagent model configuration (inherits the main model when omitted).
- **middleware** Additional middleware to attach to the subagent. See [here](https://docs.langchain.com/oss/python/langchain/middleware) for an introduction into middleware and how it works with create_agent.

**CustomSubAgent fields:**
- **name**: This is the name of the subagent, and how the main agent will call the subagent
- **description**: This is the description of the subagent that is shown to the main agent
- **graph**: A pre-built LangGraph graph/agent that will be used as the subagent

#### Using SubAgent

```python
research_subagent = {
    "name": "research-agent",
    "description": "Used to research more in depth questions",
    "prompt": sub_research_prompt,
    "tools": [internet_search]
}
subagents = [research_subagent]
agent = create_deep_agent(
    tools,
    prompt,
    subagents=subagents
)
```

#### Using CustomSubAgent

For more complex use cases, you can provide your own pre-built LangGraph graph as a subagent:

```python
from langchain.agents import create_agent

# Create a custom agent graph
custom_graph = create_agent(
    model=your_model,
    tools=specialized_tools,
    prompt="You are a specialized agent for data analysis..."
)

# Use it as a custom subagent
custom_subagent = {
    "name": "data-analyzer",
    "description": "Specialized agent for complex data analysis tasks",
    "graph": custom_graph
}

subagents = [custom_subagent]
agent = create_deep_agent(
    tools,
    prompt,
    subagents=subagents
)
```

### `model` (Optional)

By default, `deepagents` uses `"claude-sonnet-4-20250514"`. You can customize this by passing any [LangChain model object](https://python.langchain.com/docs/integrations/chat/).

#### Example: Using a Custom Model

Here's how to use a custom model (like OpenAI's `gpt-oss` model via Ollama):

(Requires `pip install langchain` and then `pip install langchain-ollama` for Ollama models)

```python
from deepagents import create_deep_agent

# ... existing agent definitions ...

model = init_chat_model(
    model="ollama:gpt-oss:20b",  
)
agent = create_deep_agent(
    tools=tools,
    instructions=instructions,
    model=model,
    ...
)
```

#### Example: Per-subagent model override (optional)

Use a fast, deterministic model for a critique sub-agent, while keeping a different default model for the main agent and others:

```python
from deepagents import create_deep_agent

critique_sub_agent = {
    "name": "critique-agent",
    "description": "Critique the final report",
    "prompt": "You are a tough editor.",
    "model_settings": {
        "model": "anthropic:claude-3-5-haiku-20241022",
        "temperature": 0,
        "max_tokens": 8192
    }
}

agent = create_deep_agent(
    tools=[internet_search],
    instructions="You are an expert researcher...",
    model="claude-sonnet-4-20250514",  # default for main agent and other sub-agents
    subagents=[critique_sub_agent],
)
```


### `middleware` (Optional)
Both the main agent and sub-agents can take additional custom AgentMiddleware. Middleware is the best supported approach for extending the state_schema, adding additional tools, and adding pre / post model hooks. See this [doc](https://docs.langchain.com/oss/python/langchain/middleware) to learn more about Middleware and how you can use it!

### `tool_configs` (Optional)
Tool configs are used to specify how to handle Human In The Loop interactions on certain tools that require additional human oversight.

These tool_configs are passed to our prebuilt [HITL middleware](https://docs.langchain.com/oss/python/langchain/middleware#human-in-the-loop) so that the agent pauses execution and waits for feedback from the user before executing configured tools.

## Deep Agent Details

The below components are built into `deepagents` and helps make it work for deep tasks off-the-shelf.

### System Prompt

`deepagents` comes with a [built-in system prompt](src/deepagents/prompts.py). This is relatively detailed prompt that is heavily based on and inspired by [attempts](https://github.com/kn1026/cc/blob/main/claudecode.md) to [replicate](https://github.com/asgeirtj/system_prompts_leaks/blob/main/Anthropic/claude-code.md)
Claude Code's system prompt. It was made more general purpose than Claude Code's system prompt.
This contains detailed instructions for how to use the built-in planning tool, file system tools, and sub agents.
Note that part of this system prompt [can be customized](#instructions-required)

Without this default system prompt - the agent would not be nearly as successful at going as it is.
The importance of prompting for creating a "deep" agent cannot be understated.

### Planning Tool

`deepagents` comes with a built-in planning tool. This planning tool is very simple and is based on ClaudeCode's TodoWrite tool.
This tool doesn't actually do anything - it is just a way for the agent to come up with a plan, and then have that in the context to help keep it on track.

### File System Tools

`deepagents` comes with four built-in file system tools: `ls`, `edit_file`, `read_file`, `write_file`.
These do not actually use a file system - rather, they mock out a file system using LangGraph's State object.
This means you can easily run many of these agents on the same machine without worrying that they will edit the same underlying files.

Right now the "file system" will only be one level deep (no sub directories).

These files can be passed in (and also retrieved) by using the `files` key in the LangGraph State object.

```python
agent = create_deep_agent(...)

result = agent.invoke({
    "messages": ...,
    # Pass in files to the agent using this key
    # "files": {"foo.txt": "foo", ...}
})

# Access any files afterwards like this
result["files"]
```

### Sub Agents

`deepagents` comes with the built-in ability to call sub agents (based on Claude Code).
It has access to a `general-purpose` subagent at all times - this is a subagent with the same instructions as the main agent and all the tools that is has access to.
You can also specify [custom sub agents](#subagents-optional) with their own instructions and tools.

Sub agents are useful for ["context quarantine"](https://www.dbreunig.com/2025/06/26/how-to-fix-your-context.html#context-quarantine) (to help not pollute the overall context of the main agent)
as well as custom instructions.

### Built In Tools

By default, deep agents come with five built-in tools:

- `write_todos`: Tool for writing todos
- `write_file`: Tool for writing to a file in the virtual filesystem
- `read_file`: Tool for reading from a file in the virtual filesystem
- `ls`: Tool for listing files in the virtual filesystem
- `edit_file`: Tool for editing a file in the virtual filesystem

If you want to omit some deepagents functionality, use specific middleware components directly!

### Human-in-the-Loop

`deepagents` supports human-in-the-loop approval for tool execution. You can configure specific tools to require human approval before execution using the `tool_configs` parameter, which maps tool names to a `HumanInTheLoopConfig`.

`HumanInTheLoopConfig` is how you specify what type of human in the loop patterns are supported.
It is a dictionary with four specific keys:

- `allow_accept`: Whether the human can approve the current action without changes
- `allow_respond`: Whether the human can reject the current action with feedback
- `allow_edit`: Whether the human can approve the current action with edited content

Instead of specifying a `HumanInTheLoopConfig` for a tool, you can also just set `True`. This will set `allow_ignore`, `allow_respond`, `allow_edit`, and `allow_accept` to be `True`.

In order to use human in the loop, you need to have a checkpointer attached.
Note: if you are using LangGraph Platform, this is automatically attached.

Example usage:

```python
from deepagents import create_deep_agent
from langgraph.checkpoint.memory import InMemorySaver

# Create agent with file operations requiring approval
agent = create_deep_agent(
    tools=[your_tools],
    instructions="Your instructions here",
    tool_configs={
        # You can specify a dictionary for fine grained control over what interrupt options exist
        "tool_1": {
            "allow_respond": True,
            "allow_edit": True,
            "allow_accept":True,
        },
        # You can specify a boolean for shortcut
        # This is a shortcut for the same functionality as above
        "tool_2": True,
    }
)

checkpointer= InMemorySaver()
agent.checkpointer = checkpointer
```

#### Approve

To "approve" a tool call means the agent will execute the tool call as is.

This flow shows how to approve a tool call (assuming the tool requiring approval is called):

```python
config = {"configurable": {"thread_id": "1"}}
for s in agent.stream({"messages": [{"role": "user", "content": message}]}, config=config):
    print(s)
# If this calls a tool with an interrupt, this will then return an interrupt
for s in agent.stream(Command(resume=[{"type": "accept"}]), config=config):
    print(s)

```

#### Edit

To "edit" a tool call means the agent will execute the new tool with the new arguments. You can change both the tool to call or the arguments to pass to that tool.

The `args` parameter you pass back should be a dictionary with two keys:

- `action`: maps to a string which is the name of the tool to call
- `args`: maps to a dictionary which is the arguments to pass to the tool

This flow shows how to edit a tool call (assuming the tool requiring approval is called):

```python
config = {"configurable": {"thread_id": "1"}}
for s in agent.stream({"messages": [{"role": "user", "content": message}]}, config=config):
    print(s)
# If this calls a tool with an interrupt, this will then return an interrupt
# Replace the `...` with the tool name you want to call, and the arguments
for s in agent.stream(Command(resume=[{"type": "edit", "args": {"action": "...", "args": {...}}}]), config=config):
    print(s)

```

#### Respond

To "respond" to a tool call means that tool is NOT called. Rather, a tool message is appended with the content you respond with, and the updated messages list is then sent back to the model.

The `args` parameter you pass back should be a string with your response.

This flow shows how to respond to a tool call (assuming the tool requiring approval is called):

```python
config = {"configurable": {"thread_id": "1"}}
for s in agent.stream({"messages": [{"role": "user", "content": message}]}, config=config):
    print(s)
# If this calls a tool with an interrupt, this will then return an interrupt
# Replace the `...` with the response to use all the ToolMessage content
for s in agent.stream(Command(resume=[{"type": "response", "args": "..."}]), config=config):
    print(s)

```
## Async

If you are passing async tools to your agent, you will want to use `from deepagents import async_create_deep_agent`
## MCP

The `deepagents` library can be ran with MCP tools. This can be achieved by using the [Langchain MCP Adapter library](https://github.com/langchain-ai/langchain-mcp-adapters).

**NOTE:** You will want to use `from deepagents import async_create_deep_agent` to use the async version of `deepagents`, since MCP tools are async

(To run the example below, will need to `pip install langchain-mcp-adapters`)

```python
import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient
from deepagents import create_deep_agent

async def main():
    # Collect MCP tools
    mcp_client = MultiServerMCPClient(...)
    mcp_tools = await mcp_client.get_tools()

    # Create agent
    agent = async_create_deep_agent(tools=mcp_tools, ....)

    # Stream the agent
    async for chunk in agent.astream(
        {"messages": [{"role": "user", "content": "what is langgraph?"}]},
        stream_mode="values"
    ):
        if "messages" in chunk:
            chunk["messages"][-1].pretty_print()

asyncio.run(main())
```

## Roadmap
- [ ] Allow users to customize full system prompt
- [ ] Code cleanliness (type hinting, docstrings, formating)
- [ ] Allow for more of a robust virtual filesystem
- [ ] Create an example of a deep coding agent built on top of this
- [ ] Benchmark the example of [deep research agent](examples/research/research_agent.py)



================================================
FILE: examples/research/research_agent.py
================================================
import os
from typing import Literal

from tavily import TavilyClient

from deepagents import create_deep_agent

# It's best practice to initialize the client once and reuse it.
tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

# Search tool to use to do research
def internet_search(
query: str,
max_results: int = 5,
topic: Literal["general", "news", "finance"] = "general",
include_raw_content: bool = False,
):
"""Run a web search"""
search_docs = tavily_client.search(
query,
max_results=max_results,
include_raw_content=include_raw_content,
topic=topic,
)
return search_docs


sub_research_prompt = """You are a dedicated researcher. Your job is to conduct research based on the users questions.

Conduct thorough research and then reply to the user with a detailed answer to their question

only your FINAL answer will be passed on to the user. They will have NO knowledge of anything except your final message, so your final report should be your final message!"""

research_sub_agent = {
"name": "research-agent",
"description": "Used to research more in depth questions. Only give this researcher one topic at a time. Do not pass multiple sub questions to this researcher. Instead, you should break down a large topic into the necessary components, and then call multiple research agents in parallel, one for each sub question.",
"prompt": sub_research_prompt,
"tools": [internet_search],
}

sub_critique_prompt = """You are a dedicated editor. You are being tasked to critique a report.

You can find the report at `final_report.md`.

You can find the question/topic for this report at `question.txt`.

The user may ask for specific areas to critique the report in. Respond to the user with a detailed critique of the report. Things that could be improved.

You can use the search tool to search for information, if that will help you critique the report

Do not write to the `final_report.md` yourself.

Things to check:
- Check that each section is appropriately named
- Check that the report is written as you would find in an essay or a textbook - it should be text heavy, do not let it just be a list of bullet points!
- Check that the report is comprehensive. If any paragraphs or sections are short, or missing important details, point it out.
- Check that the article covers key areas of the industry, ensures overall understanding, and does not omit important parts.
- Check that the article deeply analyzes causes, impacts, and trends, providing valuable insights
- Check that the article closely follows the research topic and directly answers questions
- Check that the article has a clear structure, fluent language, and is easy to understand.
  """

critique_sub_agent = {
"name": "critique-agent",
"description": "Used to critique the final report. Give this agent some information about how you want it to critique the report.",
"prompt": sub_critique_prompt,
}


# Prompt prefix to steer the agent to be an expert researcher
research_instructions = """You are an expert researcher. Your job is to conduct thorough research, and then write a polished report.

The first thing you should do is to write the original user question to `question.txt` so you have a record of it.

Use the research-agent to conduct deep research. It will respond to your questions/topics with a detailed answer.

When you think you enough information to write a final report, write it to `final_report.md`

You can call the critique-agent to get a critique of the final report. After that (if needed) you can do more research and edit the `final_report.md`
You can do this however many times you want until are you satisfied with the result.

Only edit the file once at a time (if you call this tool in parallel, there may be conflicts).

Here are instructions for writing the final report:

<report_instructions>

CRITICAL: Make sure the answer is written in the same language as the human messages! If you make a todo plan - you should note in the plan what language the report should be in so you dont forget!
Note: the language the report should be in is the language the QUESTION is in, not the language/country that the question is ABOUT.

Please create a detailed answer to the overall research brief that:
1. Is well-organized with proper headings (# for title, ## for sections, ### for subsections)
2. Includes specific facts and insights from the research
3. References relevant sources using [Title](URL) format
4. Provides a balanced, thorough analysis. Be as comprehensive as possible, and include all information that is relevant to the overall research question. People are using you for deep research and will expect detailed, comprehensive answers.
5. Includes a "Sources" section at the end with all referenced links

You can structure your report in a number of different ways. Here are some examples:

To answer a question that asks you to compare two things, you might structure your report like this:
1/ intro
2/ overview of topic A
3/ overview of topic B
4/ comparison between A and B
5/ conclusion

To answer a question that asks you to return a list of things, you might only need a single section which is the entire list.
1/ list of things or table of things
Or, you could choose to make each item in the list a separate section in the report. When asked for lists, you don't need an introduction or conclusion.
1/ item 1
2/ item 2
3/ item 3

To answer a question that asks you to summarize a topic, give a report, or give an overview, you might structure your report like this:
1/ overview of topic
2/ concept 1
3/ concept 2
4/ concept 3
5/ conclusion

If you think you can answer the question with a single section, you can do that too!
1/ answer

REMEMBER: Section is a VERY fluid and loose concept. You can structure your report however you think is best, including in ways that are not listed above!
Make sure that your sections are cohesive, and make sense for the reader.

For each section of the report, do the following:
- Use simple, clear language
- Use ## for section title (Markdown format) for each section of the report
- Do NOT ever refer to yourself as the writer of the report. This should be a professional report without any self-referential language.
- Do not say what you are doing in the report. Just write the report without any commentary from yourself.
- Each section should be as long as necessary to deeply answer the question with the information you have gathered. It is expected that sections will be fairly long and verbose. You are writing a deep research report, and users will expect a thorough answer.
- Use bullet points to list out information when appropriate, but by default, write in paragraph form.

REMEMBER:
The brief and research may be in English, but you need to translate this information to the right language when writing the final answer.
Make sure the final answer report is in the SAME language as the human messages in the message history.

Format the report in clear markdown with proper structure and include source references where appropriate.

<Citation Rules>
- Assign each unique URL a single citation number in your text
- End with ### Sources that lists each source with corresponding numbers
- IMPORTANT: Number sources sequentially without gaps (1,2,3,4...) in the final list regardless of which sources you choose
- Each source should be a separate line item in a list, so that in markdown it is rendered as a list.
- Example format:
  [1] Source Title: URL
  [2] Source Title: URL
- Citations are extremely important. Make sure to include these, and pay a lot of attention to getting these right. Users will often use these citations to look into more information.
</Citation Rules>
</report_instructions>

You have access to a few tools.

## `internet_search`

Use this to run an internet search for a given query. You can specify the number of results, the topic, and whether raw content should be included.
"""

# Create the agent
agent = create_deep_agent(
tools=[internet_search],
instructions=research_instructions,
subagents=[critique_sub_agent, research_sub_agent],
).with_config({"recursion_limit": 1000})



================================================
FILE: src/deepagents/graph.py
================================================
from typing import Sequence, Union, Callable, Any, Type, Optional
from langchain_core.tools import BaseTool
from langchain_core.language_models import LanguageModelLike
from langgraph.types import Checkpointer
from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, SummarizationMiddleware, HumanInTheLoopMiddleware
from langchain.agents.middleware.human_in_the_loop import ToolConfig
from langchain.agents.middleware.prompt_caching import AnthropicPromptCachingMiddleware
from deepagents.middleware import PlanningMiddleware, FilesystemMiddleware, SubAgentMiddleware
from deepagents.prompts import BASE_AGENT_PROMPT
from deepagents.model import get_default_model
from deepagents.types import SubAgent, CustomSubAgent

def agent_builder(
tools: Sequence[Union[BaseTool, Callable, dict[str, Any]]],
instructions: str,
middleware: Optional[list[AgentMiddleware]] = None,
tool_configs: Optional[dict[str, bool | ToolConfig]] = None,
model: Optional[Union[str, LanguageModelLike]] = None,
subagents: Optional[list[SubAgent | CustomSubAgent]] = None,
context_schema: Optional[Type[Any]] = None,
checkpointer: Optional[Checkpointer] = None,
is_async: bool = False,
):
if model is None:
model = get_default_model()

    deepagent_middleware = [
        PlanningMiddleware(),
        FilesystemMiddleware(),
        SubAgentMiddleware(
            default_subagent_tools=tools,   # NOTE: These tools are piped to the general-purpose subagent.
            subagents=subagents if subagents is not None else [],
            model=model,
            is_async=is_async,
        ),
        SummarizationMiddleware(
            model=model,
            max_tokens_before_summary=120000,
            messages_to_keep=20,
        ),
        AnthropicPromptCachingMiddleware(ttl="5m", unsupported_model_behavior="ignore")
    ]
    # Add tool interrupt config if provided
    if tool_configs is not None:
        deepagent_middleware.append(HumanInTheLoopMiddleware(interrupt_on=tool_configs))

    if middleware is not None:
        deepagent_middleware.extend(middleware)

    return create_agent(
        model,
        system_prompt=instructions + "\n\n" + BASE_AGENT_PROMPT,
        tools=tools,
        middleware=deepagent_middleware,
        context_schema=context_schema,
        checkpointer=checkpointer,
    )

def create_deep_agent(
tools: Sequence[Union[BaseTool, Callable, dict[str, Any]]] = [],
instructions: str = "",
middleware: Optional[list[AgentMiddleware]] = None,
model: Optional[Union[str, LanguageModelLike]] = None,
subagents: Optional[list[SubAgent | CustomSubAgent]] = None,
context_schema: Optional[Type[Any]] = None,
checkpointer: Optional[Checkpointer] = None,
tool_configs: Optional[dict[str, bool | ToolConfig]] = None,
):
"""Create a deep agent.
This agent will by default have access to a tool to write todos (write_todos),
four file editing tools: write_file, ls, read_file, edit_file, and a tool to call subagents.
Args:
tools: The tools the agent should have access to.
instructions: The additional instructions the agent should have. Will go in
the system prompt.
model: The model to use.
subagents: The subagents to use. Each subagent should be a dictionary with the
following keys:
- `name`
- `description` (used by the main agent to decide whether to call the sub agent)
- `prompt` (used as the system prompt in the subagent)
- (optional) `tools`
- (optional) `model` (either a LanguageModelLike instance or dict settings)
- (optional) `middleware` (list of AgentMiddleware)
context_schema: The schema of the deep agent.
checkpointer: Optional checkpointer for persisting agent state between runs.
tool_configs: Optional Dict[str, HumanInTheLoopConfig] mapping tool names to interrupt configs.
"""
return agent_builder(
tools=tools,
instructions=instructions,
middleware=middleware,
model=model,
subagents=subagents,
context_schema=context_schema,
checkpointer=checkpointer,
tool_configs=tool_configs,
is_async=False,
)

def async_create_deep_agent(
tools: Sequence[Union[BaseTool, Callable, dict[str, Any]]] = [],
instructions: str = "",
middleware: Optional[list[AgentMiddleware]] = None,
model: Optional[Union[str, LanguageModelLike]] = None,
subagents: Optional[list[SubAgent | CustomSubAgent]] = None,
context_schema: Optional[Type[Any]] = None,
checkpointer: Optional[Checkpointer] = None,
tool_configs: Optional[dict[str, bool | ToolConfig]] = None,
):
"""Create a deep agent.
This agent will by default have access to a tool to write todos (write_todos),
four file editing tools: write_file, ls, read_file, edit_file, and a tool to call subagents.
Args:
tools: The tools the agent should have access to.
instructions: The additional instructions the agent should have. Will go in
the system prompt.
model: The model to use.
subagents: The subagents to use. Each subagent should be a dictionary with the
following keys:
- `name`
- `description` (used by the main agent to decide whether to call the sub agent)
- `prompt` (used as the system prompt in the subagent)
- (optional) `tools`
- (optional) `model` (either a LanguageModelLike instance or dict settings)
- (optional) `middleware` (list of AgentMiddleware)
context_schema: The schema of the deep agent.
checkpointer: Optional checkpointer for persisting agent state between runs.
tool_configs: Optional Dict[str, HumanInTheLoopConfig] mapping tool names to interrupt configs.
"""
return agent_builder(
tools=tools,
instructions=instructions,
middleware=middleware,
model=model,
subagents=subagents,
context_schema=context_schema,
checkpointer=checkpointer,
tool_configs=tool_configs,
is_async=True,
)


================================================
FILE: src/deepagents/middleware.py
================================================
"""DeepAgents implemented as Middleware"""

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, AgentState, ModelRequest, SummarizationMiddleware
from langchain.agents.middleware.prompt_caching import AnthropicPromptCachingMiddleware
from langchain_core.tools import BaseTool, tool, InjectedToolCallId
from langchain_core.messages import ToolMessage
from langchain.chat_models import init_chat_model
from langgraph.types import Command
from langgraph.runtime import Runtime
from langchain.tools.tool_node import InjectedState
from typing import Annotated
from deepagents.state import PlanningState, FilesystemState
from deepagents.tools import write_todos, ls, read_file, write_file, edit_file
from deepagents.prompts import WRITE_TODOS_SYSTEM_PROMPT, TASK_SYSTEM_PROMPT, FILESYSTEM_SYSTEM_PROMPT, TASK_TOOL_DESCRIPTION, BASE_AGENT_PROMPT
from deepagents.types import SubAgent, CustomSubAgent

###########################
# Planning Middleware
###########################

class PlanningMiddleware(AgentMiddleware):
state_schema = PlanningState
tools = [write_todos]

    def modify_model_request(self, request: ModelRequest, agent_state: PlanningState, runtime: Runtime) -> ModelRequest:
        request.system_prompt = request.system_prompt + "\n\n" + WRITE_TODOS_SYSTEM_PROMPT
        return request

###########################
# Filesystem Middleware
###########################

class FilesystemMiddleware(AgentMiddleware):
state_schema = FilesystemState
tools = [ls, read_file, write_file, edit_file]

    def modify_model_request(self, request: ModelRequest, agent_state: FilesystemState, runtime: Runtime) -> ModelRequest:
        request.system_prompt = request.system_prompt + "\n\n" + FILESYSTEM_SYSTEM_PROMPT
        return request

###########################
# SubAgent Middleware
###########################

class SubAgentMiddleware(AgentMiddleware):
def __init__(
self,
default_subagent_tools: list[BaseTool] = [],
subagents: list[SubAgent | CustomSubAgent] = [],
model=None,
is_async=False,
) -> None:
super().__init__()
task_tool = create_task_tool(
default_subagent_tools=default_subagent_tools,
subagents=subagents,
model=model,
is_async=is_async,
)
self.tools = [task_tool]

    def modify_model_request(self, request: ModelRequest, agent_state: AgentState, runtime: Runtime) -> ModelRequest:
        request.system_prompt = request.system_prompt + "\n\n" + TASK_SYSTEM_PROMPT
        return request

def _get_agents(
default_subagent_tools: list[BaseTool],
subagents: list[SubAgent | CustomSubAgent],
model
):
default_subagent_middleware = [
PlanningMiddleware(),
FilesystemMiddleware(),
# TODO: Add this back when fixed
SummarizationMiddleware(
model=model,
max_tokens_before_summary=120000,
messages_to_keep=20,
),
AnthropicPromptCachingMiddleware(ttl="5m", unsupported_model_behavior="ignore"),
]
agents = {
"general-purpose": create_agent(
model,
system_prompt=BASE_AGENT_PROMPT,
tools=default_subagent_tools,
checkpointer=False,
middleware=default_subagent_middleware
)
}
for _agent in subagents:
if "graph" in _agent:
agents[_agent["name"]] = _agent["graph"]
continue
if "tools" in _agent:
_tools = _agent["tools"]
else:
_tools = default_subagent_tools.copy()
# Resolve per-subagent model: can be instance or dict
if "model" in _agent:
agent_model = _agent["model"]
if isinstance(agent_model, dict):
# Dictionary settings - create model from config
sub_model = init_chat_model(**agent_model)
else:
# Model instance - use directly
sub_model = agent_model
else:
# Fallback to main model
sub_model = model
if "middleware" in _agent:
_middleware = [*default_subagent_middleware, *_agent["middleware"]]
else:
_middleware = default_subagent_middleware
agents[_agent["name"]] = create_agent(
sub_model,
system_prompt=_agent["prompt"],
tools=_tools,
middleware=_middleware,
checkpointer=False,
)
return agents


def _get_subagent_description(subagents: list[SubAgent | CustomSubAgent]):
return [f"- {_agent['name']}: {_agent['description']}" for _agent in subagents]


def create_task_tool(
default_subagent_tools: list[BaseTool],
subagents: list[SubAgent | CustomSubAgent],
model,
is_async: bool = False,
):
agents = _get_agents(
default_subagent_tools, subagents, model
)
other_agents_string = _get_subagent_description(subagents)

    if is_async:
        @tool(
            description=TASK_TOOL_DESCRIPTION.format(other_agents=other_agents_string)
        )
        async def task(
            description: str,
            subagent_type: str,
            state: Annotated[dict, InjectedState],
            tool_call_id: Annotated[str, InjectedToolCallId],
        ):
            if subagent_type not in agents:
                return f"Error: invoked agent of type {subagent_type}, the only allowed types are {[f'`{k}`' for k in agents]}"
            sub_agent = agents[subagent_type]
            state["messages"] = [{"role": "user", "content": description}]
            result = await sub_agent.ainvoke(state)
            state_update = {}
            for k, v in result.items():
                if k not in ["todos", "messages"]:
                    state_update[k] = v
            return Command(
                update={
                    **state_update,
                    "messages": [
                        ToolMessage(
                            result["messages"][-1].content, tool_call_id=tool_call_id
                        )
                    ],
                }
            )
    else: 
        @tool(
            description=TASK_TOOL_DESCRIPTION.format(other_agents=other_agents_string)
        )
        def task(
            description: str,
            subagent_type: str,
            state: Annotated[dict, InjectedState],
            tool_call_id: Annotated[str, InjectedToolCallId],
        ):
            if subagent_type not in agents:
                return f"Error: invoked agent of type {subagent_type}, the only allowed types are {[f'`{k}`' for k in agents]}"
            sub_agent = agents[subagent_type]
            state["messages"] = [{"role": "user", "content": description}]
            result = sub_agent.invoke(state)
            state_update = {}
            for k, v in result.items():
                if k not in ["todos", "messages"]:
                    state_update[k] = v
            return Command(
                update={
                    **state_update,
                    "messages": [
                        ToolMessage(
                            result["messages"][-1].content, tool_call_id=tool_call_id
                        )
                    ],
                }
            )
    return task



================================================
FILE: src/deepagents/model.py
================================================
from langchain_anthropic import ChatAnthropic


def get_default_model():
return ChatAnthropic(model_name="claude-sonnet-4-20250514", max_tokens=64000)



================================================
FILE: src/deepagents/prompts.py
================================================
WRITE_TODOS_TOOL_DESCRIPTION = """Use this tool to create and manage a structured task list for your current work session. This helps you track progress, organize complex tasks, and demonstrate thoroughness to the user.
It also helps the user understand the progress of the task and overall progress of their requests.
Only use this tool if you think it will be helpful in staying organized. If the user's request is trivial and takes less than 3 steps, it is better to NOT use this tool and just do the taks directly.

## When to Use This Tool
Use this tool in these scenarios:

1. Complex multi-step tasks - When a task requires 3 or more distinct steps or actions
2. Non-trivial and complex tasks - Tasks that require careful planning or multiple operations
3. User explicitly requests todo list - When the user directly asks you to use the todo list
4. User provides multiple tasks - When users provide a list of things to be done (numbered or comma-separated)
5. The plan may need future revisions or updates based on results from the first few steps. Keeping track of this in a list is helpful.

## How to Use This Tool
1. When you start working on a task - Mark it as in_progress BEFORE beginning work.
2. After completing a task - Mark it as completed and add any new follow-up tasks discovered during implementation.
3. You can also update future tasks, such as deleting them if they are no longer necessary, or adding new tasks that are necessary. Don't change previously completed tasks.
4. You can make several updates to the todo list at once. For example, when you complete a task, you can mark the next task you need to start as in_progress.

## When NOT to Use This Tool
It is important to skip using this tool when:
1. There is only a single, straightforward task
2. The task is trivial and tracking it provides no benefit
3. The task can be completed in less than 3 trivial steps
4. The task is purely conversational or informational

## Examples of When to Use the Todo List

<example>
User: I want to add a dark mode toggle to the application settings. Make sure you run the tests and build when you're done!
Assistant: I'll help add a dark mode toggle to your application settings. Let me create a todo list to track this implementation.
*Creates todo list with the following items:*
1. Create dark mode toggle component in Settings page
2. Add dark mode state management (context/store)
3. Implement CSS-in-JS styles for dark theme
4. Update existing components to support theme switching
5. Run tests and build process, addressing any failures or errors that occur
*Begins working on the first task*

<reasoning>
The assistant used the todo list because:
1. Adding dark mode in it of itself is a multi-step feature requiring UI, state management, and styling changes
2. The assistant inferred that tests and build need to pass by adding "Ensure tests and build succeed" as the final task
3. Both of the user's requests are complex and require multiple steps to complete.
</reasoning>
</example>

<example>
User: Help me plan a comprehensive marketing campaign for our new product launch, including social media, email marketing, and press releases.
Assistant: I'll help you plan a comprehensive marketing campaign for your product launch. Let me create a todo list to organize all the components.
*Creates todo list with the following items:*
1. Define target audience and key messaging
2. Create social media content calendar and posting schedule
3. Design email marketing sequence and automation flows
4. Draft press release and identify media contacts
5. Set up tracking and analytics for campaign performance
6. Create visual assets and brand materials
7. Coordinate launch timeline and deliverables
*Begins working on the first task*

<reasoning>
The assistant used the todo list because:
1. Marketing campaign planning involves multiple distinct channels and activities
2. Each component requires careful coordination and planning
3. The systematic approach ensures all aspects of the launch are covered
</reasoning>
</example>

<example>
User: Help me rename the function getCwd to getCurrentWorkingDirectory across my project
Assistant: Let me first search through your codebase to find all occurrences of 'getCwd'.
*Uses search tools to locate all instances of getCwd in the codebase*
Assistant: I've found 15 instances of 'getCwd' across 8 different files. Let me create a todo list to track these changes.
*Creates todo list with specific items for each file that needs updating*

<reasoning>
The assistant used the todo list because:
1. The assistant searched to understand the scope of the task
2. Upon finding multiple occurrences across different files, it determined this was a complex task with multiple steps (>3)
3. The todo list helps ensure every instance is tracked and updated systematically
4. This approach prevents missing any occurrences and maintains consistency.
</reasoning>
</example>

<example>
User: I need help organizing my home office: decluttering the desk, setting up a filing system, organizing digital files, and creating a daily workflow.
Assistant: I'll help you organize your home office systematically. Let me create a todo list to track each area of organization.
*Creates todo list with items like: 1) Sort and declutter desk items, 2) Set up physical filing system for documents, 3) Organize digital files and folders, 4) Create daily workflow and productivity systems, 5) Establish maintenance routines*
Let's start with decluttering your desk space to create a clean foundation for the other organizational systems.

<reasoning>
The assistant used the todo list because:
1. The user provided multiple distinct organizational tasks
2. Each area requires different approaches and careful planning
3. Home organization benefits from systematic, step-by-step completion
4. Progress tracking ensures all areas are addressed thoroughly
</reasoning>
</example>

## Examples of When NOT to Use the Todo List

<example>
User: How do I print 'Hello World' in Python?
Assistant: In Python, you can print "Hello World" with this simple code:

python
print("Hello World")

This will output the text "Hello World" to the console when executed.</assistant>

<reasoning>
The assistant did not use the todo list because this is a single, trivial task that can be completed in one step. There's no need to track multiple tasks or steps for such a straightforward request.
</reasoning>
</example>

<example>
User: What's the best way to water houseplants?
Assistant: The best way to water houseplants depends on the specific plant type, but here are some general guidelines:

- Check soil moisture by inserting your finger about 1-2 inches into the soil
- Water thoroughly when the top inch feels dry, allowing water to drain from the bottom
- Use room temperature water and water in the morning when possible
- Avoid overwatering, which is more harmful than underwatering for most plants

Different plants have different needs, so it's important to research your specific varieties for optimal care.

<reasoning>
The assistant did not use the todo list because this is an informational request with no actual tasks to complete. The user is simply asking for advice and explanation, not for the assistant to perform multiple steps or activities.
</reasoning>
</example>

<example>
User: Can you add a comment to the calculateTotal function to explain what it does?
Assistant: Sure, let me add a comment to the calculateTotal function to explain what it does.
* Uses the Edit tool to add a comment to the calculateTotal function *

<reasoning>
The assistant did not use the todo list because this is a single, straightforward task confined to one location. Adding a comment doesn't require tracking multiple steps or systematic organization.
</reasoning>
</example>

<example>
User: What time is it in Tokyo right now?
Assistant: I'll check the current time in Tokyo for you.

*Searches for current time in Tokyo*

The current time in Tokyo, Japan is [current time]. Tokyo is in the Japan Standard Time (JST) zone, which is UTC+9.

<reasoning>
The assistant did not use the todo list because this is a single information lookup with immediate results. There are no multiple steps to track or organize, making the todo list unnecessary for this straightforward request.
</reasoning>
</example>

<example>
User: I need to write a function that checks if a number is prime and then test it out.
Assistant: I'll help you write a function that checks if a number is prime and then test it out.
*Writes function that checks if a number is prime*
*Tests the function*

<reasoning>
Even though this is a multi-step task, it is very straightforward and can be completed in two trivial steps (which is less than 3 steps!). Using the todo list here is overkill and wastes time and tokens.
</reasoning>
</example>

<example>
User: I want you to order a pizza from Dominos, order a burger from McDonald's, and order a salad from Subway.
Assistant: I'll help you order a pizza from Dominos, order a burger from McDonald's, and order a salad from Subway.
*Orders a pizza from Dominos*
*Orders a burger from McDonald's*
*Orders a salad from Subway*

<reasoning>
Even though this is a multi-step task, assuming the assistant has the ability to order from these restaurants, it is very straightforward and can be completed in three trivial tool calls. 
Using the todo list here is overkill and wastes time and tokens. These three tool calls should be made in parallel, in fact.
</reasoning>
</example>


## Task States and Management

1. **Task States**: Use these states to track progress:
    - pending: Task not yet started
    - in_progress: Currently working on (you can have multiple tasks in_progress at a time if they are not related to each other and can be run in parallel)
    - completed: Task finished successfully

2. **Task Management**:
    - Update task status in real-time as you work
    - Mark tasks complete IMMEDIATELY after finishing (don't batch completions)
    - Complete current tasks before starting new ones
    - Remove tasks that are no longer relevant from the list entirely
    - IMPORTANT: When you write this todo list, you should mark your first task (or tasks) as in_progress immediately!.
    - IMPORTANT: Unless all tasks are completed, you should always have at least one task in_progress to show the user that you are working on something.

3. **Task Completion Requirements**:
    - ONLY mark a task as completed when you have FULLY accomplished it
    - If you encounter errors, blockers, or cannot finish, keep the task as in_progress
    - When blocked, create a new task describing what needs to be resolved
    - Never mark a task as completed if:
        - There are unresolved issues or errors
        - Work is partial or incomplete
        - You encountered blockers that prevent completion
        - You couldn't find necessary resources or dependencies
        - Quality standards haven't been met

4. **Task Breakdown**:
    - Create specific, actionable items
    - Break complex tasks into smaller, manageable steps
    - Use clear, descriptive task names

Being proactive with task management demonstrates attentiveness and ensures you complete all requirements successfully
Remember: If you only need to make a few tool calls to complete a task, and it is clear what you need to do, it is better to just do the task directly and NOT call this tool at all.
"""

TASK_TOOL_DESCRIPTION = """Launch an ephemeral subagent to handle complex, multi-step independent tasks with isolated context windows.

Available agent types and the tools they have access to:
- general-purpose: General-purpose agent for researching complex questions, searching for files and content, and executing multi-step tasks. When you are searching for a keyword or file and are not confident that you will find the right match in the first few tries use this agent to perform the search for you. This agent has access to all tools as the main agent.
  {other_agents}

When using the Task tool, you must specify a subagent_type parameter to select which agent type to use.

## Usage notes:
1. Launch multiple agents concurrently whenever possible, to maximize performance; to do that, use a single message with multiple tool uses
2. When the agent is done, it will return a single message back to you. The result returned by the agent is not visible to the user. To show the user the result, you should send a text message back to the user with a concise summary of the result.
3. Each agent invocation is stateless. You will not be able to send additional messages to the agent, nor will the agent be able to communicate with you outside of its final report. Therefore, your prompt should contain a highly detailed task description for the agent to perform autonomously and you should specify exactly what information the agent should return back to you in its final and only message to you.
4. The agent's outputs should generally be trusted
5. Clearly tell the agent whether you expect it to create content, perform analysis, or just do research (search, file reads, web fetches, etc.), since it is not aware of the user's intent
6. If the agent description mentions that it should be used proactively, then you should try your best to use it without the user having to ask for it first. Use your judgement.
7. When only the general-purpose agent is provided, you should use it for all tasks. It is great for isolating context and token usage, and completing specific, complex tasks, as it has all the same capabilities as the main agent.

### Example usage of the general-purpose agent:

<example_agent_descriptions>
"general-purpose": use this agent for general purpose tasks, it has access to all tools as the main agent.
</example_agent_descriptions>

<example>
User: "I want to conduct research on the accomplishments of Lebron James, Michael Jordan, and Kobe Bryant, and then compare them."
Assistant: *Uses the task tool in parallel to conduct isolated research on each of the three players*
Assistant: *Synthesizes the results of the three isolated research tasks and responds to the User*
<commentary>
Research is a complex, multi-step task in it of itself.
The research of each individual player is not dependent on the research of the other players.
The assistant uses the task tool to break down the complex objective into three isolated tasks.
Each research task only needs to worry about context and tokens about one player, then returns synthesized information about each player as the Tool Result.
This means each research task can dive deep and spend tokens and context deeply researching each player, but the final result is synthesized information, and saves us tokens in the long run when comparing the players to each other.
</commentary>
</example>

<example>
User: "Analyze a single large code repository for security vulnerabilities and generate a report."
Assistant: *Launches a single `task` subagent for the repository analysis*
Assistant: *Receives report and integrates results into final summary*
<commentary>
Subagent is used to isolate a large, context-heavy task, even though there is only one. This prevents the main thread from being overloaded with details.
If the user then asks followup questions, we have a concise report to reference instead of the entire history of analysis and tool calls, which is good and saves us time and money.
</commentary>
</example>

<example>
User: "Schedule two meetings for me and prepare agendas for each."
Assistant: *Calls the task tool in parallel to launch two `task` subagents (one per meeting) to prepare agendas*
Assistant: *Returns final schedules and agendas*
<commentary>
Tasks are simple individually, but subagents help silo agenda preparation.
Each subagent only needs to worry about the agenda for one meeting.
</commentary>
</example>

<example>
User: "I want to order a pizza from Dominos, order a burger from McDonald's, and order a salad from Subway."
Assistant: *Calls tools directly in parallel to order a pizza from Dominos, a burger from McDonald's, and a salad from Subway*
<commentary>
The assistant did not use the task tool because the objective is super simple and clear and only requires a few trivial tool calls.
It is better to just complete the task directly and NOT use the `task`tool.
</commentary>
</example>

### Example usage with custom agents:

<example_agent_descriptions>
"content-reviewer": use this agent after you are done creating significant content or documents
"greeting-responder": use this agent when to respond to user greetings with a friendly joke
"research-analyst": use this agent to conduct thorough research on complex topics
</example_agent_description>

<example>
user: "Please write a function that checks if a number is prime"
assistant: Sure let me write a function that checks if a number is prime
assistant: First let me use the Write tool to write a function that checks if a number is prime
assistant: I'm going to use the Write tool to write the following code:
<code>
function isPrime(n) {{
  if (n <= 1) return false
  for (let i = 2; i * i <= n; i++) {{
    if (n % i === 0) return false
  }}
  return true
}}
</code>
<commentary>
Since significant content was created and the task was completed, now use the content-reviewer agent to review the work
</commentary>
assistant: Now let me use the content-reviewer agent to review the code
assistant: Uses the Task tool to launch with the content-reviewer agent 
</example>

<example>
user: "Can you help me research the environmental impact of different renewable energy sources and create a comprehensive report?"
<commentary>
This is a complex research task that would benefit from using the research-analyst agent to conduct thorough analysis
</commentary>
assistant: I'll help you research the environmental impact of renewable energy sources. Let me use the research-analyst agent to conduct comprehensive research on this topic.
assistant: Uses the Task tool to launch with the research-analyst agent, providing detailed instructions about what research to conduct and what format the report should take
</example>

<example>
user: "Hello"
<commentary>
Since the user is greeting, use the greeting-responder agent to respond with a friendly joke
</commentary>
assistant: "I'm going to use the Task tool to launch with the greeting-responder agent"
</example>"""

LIST_FILES_TOOL_DESCRIPTION = """Lists all files in the local filesystem.

Usage:
- The list_files tool will return a list of all files in the local filesystem.
- This is very useful for exploring the file system and finding the right file to read or edit.
- You should almost ALWAYS use this tool before using the Read or Edit tools."""

READ_FILE_TOOL_DESCRIPTION = """Reads a file from the local filesystem. You can access any file directly by using this tool.
Assume this tool is able to read all files on the machine. If the User provides a path to a file assume that path is valid. It is okay to read a file that does not exist; an error will be returned.

Usage:
- The file_path parameter must be an absolute path, not a relative path
- By default, it reads up to 2000 lines starting from the beginning of the file
- You can optionally specify a line offset and limit (especially handy for long files), but it's recommended to read the whole file by not providing these parameters
- Any lines longer than 2000 characters will be truncated
- Results are returned using cat -n format, with line numbers starting at 1
- You have the capability to call multiple tools in a single response. It is always better to speculatively read multiple files as a batch that are potentially useful.
- If you read a file that exists but has empty contents you will receive a system reminder warning in place of file contents.
- You should ALWAYS make sure a file has been read before editing it."""

EDIT_FILE_TOOL_DESCRIPTION = """Performs exact string replacements in files.

Usage:
- You must use your `Read` tool at least once in the conversation before editing. This tool will error if you attempt an edit without reading the file.
- When editing text from Read tool output, ensure you preserve the exact indentation (tabs/spaces) as it appears AFTER the line number prefix. The line number prefix format is: spaces + line number + tab. Everything after that tab is the actual file content to match. Never include any part of the line number prefix in the old_string or new_string.
- ALWAYS prefer editing existing files. NEVER write new files unless explicitly required.
- Only use emojis if the user explicitly requests it. Avoid adding emojis to files unless asked.
- The edit will FAIL if `old_string` is not unique in the file. Either provide a larger string with more surrounding context to make it unique or use `replace_all` to change every instance of `old_string`.
- Use `replace_all` for replacing and renaming strings across the file. This parameter is useful if you want to rename a variable for instance."""

WRITE_FILE_TOOL_DESCRIPTION = """Writes to a file in the local filesystem.

Usage:
- The file_path parameter must be an absolute path, not a relative path
- The content parameter must be a string
- The write_file tool will create the a new file.
- Prefer to edit existing files over creating new ones when possible."""

WRITE_TODOS_SYSTEM_PROMPT = """## `write_todos`

You have access to the `write_todos` tool to help you manage and plan complex objectives.
Use this tool for complex objectives to ensure that you are tracking each necessary step and giving the user visibility into your progress.
This tool is very helpful for planning complex objectives, and for breaking down these larger complex objectives into smaller steps.

It is critical that you mark todos as completed as soon as you are done with a step. Do not batch up multiple steps before marking them as completed.
For simple objectives that only require a few steps, it is better to just complete the objective directly and NOT use this tool.
Writing todos takes time and tokens, use it when it is helpful for managing complex many-step problems! But not for simple few-step requests.

## Important To-Do List Usage Notes to Remember
- The `write_todos` tool should never be called multiple times in parallel.
- Don't be afraid to revise the To-Do list as you go. New information may reveal new tasks that need to be done, or old tasks that are irrelevant."""

TASK_SYSTEM_PROMPT = """## `task` (subagent spawner)

You have access to a `task` tool to launch short-lived subagents that handle isolated tasks. These agents are ephemeral — they live only for the duration of the task and return a single result.

When to use the task tool:
- When a task is complex and multi-step, and can be fully delegated in isolation
- When a task is independent of other tasks and can run in parallel
- When a task requires focused reasoning or heavy token/context usage that would bloat the orchestrator thread
- When sandboxing improves reliability (e.g. code execution, structured searches, data formatting)
- When you only care about the output of the subagent, and not the intermediate steps (ex. performing a lot of research and then returned a synthesized report, performing a series of computations or lookups to achieve a concise, relevant answer.)

Subagent lifecycle:
1. **Spawn** → Provide clear role, instructions, and expected output
2. **Run** → The subagent completes the task autonomously
3. **Return** → The subagent provides a single structured result
4. **Reconcile** → Incorporate or synthesize the result into the main thread

When NOT to use the task tool:
- If you need to see the intermediate reasoning or steps after the subagent has completed (the task tool hides them)
- If the task is trivial (a few tool calls or simple lookup)
- If delegating does not reduce token usage, complexity, or context switching
- If splitting would add latency without benefit

## Important Task Tool Usage Notes to Remember
- Whenever possible, parallelize the work that you do. This is true for both tool_calls, and for tasks. Whenever you have independent steps to complete - make tool_calls, or kick off tasks (subagents) in parallel to accomplish them faster. This saves time for the user, which is incredibly important.
- Remember to use the `task` tool to silo independent tasks within a multi-part objective.
- You should use the `task` tool whenever you have a complex task that will take multiple steps, and is independent from other tasks that the agent needs to complete. These agents are highly competent and efficient."""

FILESYSTEM_SYSTEM_PROMPT = """## Filesystem Tools `ls`, `read_file`, `write_file`, `edit_file`

You have access to a local, private filesystem which you can interact with using these tools.
- ls: list all files in the local filesystem
- read_file: read a file from the local filesystem
- write_file: write to a file in the local filesystem
- edit_file: edit a file in the local filesystem"""

BASE_AGENT_PROMPT = """
In order to complete the objective that the user asks of you, you have access to a number of standard tools.
"""


================================================
FILE: src/deepagents/state.py
================================================
from langchain.agents.middleware import AgentState
from typing import NotRequired, Annotated
from typing import Literal
from typing_extensions import TypedDict


class Todo(TypedDict):
"""Todo to track."""

    content: str
    status: Literal["pending", "in_progress", "completed"]


def file_reducer(l, r):
if l is None:
return r
elif r is None:
return l
else:
return {**l, **r}


class DeepAgentState(AgentState):
todos: NotRequired[list[Todo]]
files: Annotated[NotRequired[dict[str, str]], file_reducer]


class PlanningState(AgentState):
todos: NotRequired[list[Todo]]


class FilesystemState(AgentState):
files: Annotated[NotRequired[dict[str, str]], file_reducer]


================================================
FILE: src/deepagents/tools.py
================================================
from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from langchain.tools.tool_node import InjectedState
from typing import Annotated, Union
from deepagents.state import Todo, FilesystemState
from deepagents.prompts import (
WRITE_TODOS_TOOL_DESCRIPTION,
LIST_FILES_TOOL_DESCRIPTION,
READ_FILE_TOOL_DESCRIPTION,
WRITE_FILE_TOOL_DESCRIPTION,
EDIT_FILE_TOOL_DESCRIPTION,
)


@tool(description=WRITE_TODOS_TOOL_DESCRIPTION)
def write_todos(
todos: list[Todo], tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
return Command(
update={
"todos": todos,
"messages": [
ToolMessage(f"Updated todo list to {todos}", tool_call_id=tool_call_id)
],
}
)


@tool(description=LIST_FILES_TOOL_DESCRIPTION)
def ls(state: Annotated[FilesystemState, InjectedState]) -> list[str]:
"""List all files"""
return list(state.get("files", {}).keys())


@tool(description=READ_FILE_TOOL_DESCRIPTION)
def read_file(
file_path: str,
state: Annotated[FilesystemState, InjectedState],
offset: int = 0,
limit: int = 2000,
) -> str:
mock_filesystem = state.get("files", {})
if file_path not in mock_filesystem:
return f"Error: File '{file_path}' not found"

    # Get file content
    content = mock_filesystem[file_path]

    # Handle empty file
    if not content or content.strip() == "":
        return "System reminder: File exists but has empty contents"

    # Split content into lines
    lines = content.splitlines()

    # Apply line offset and limit
    start_idx = offset
    end_idx = min(start_idx + limit, len(lines))

    # Handle case where offset is beyond file length
    if start_idx >= len(lines):
        return f"Error: Line offset {offset} exceeds file length ({len(lines)} lines)"

    # Format output with line numbers (cat -n format)
    result_lines = []
    for i in range(start_idx, end_idx):
        line_content = lines[i]

        # Truncate lines longer than 2000 characters
        if len(line_content) > 2000:
            line_content = line_content[:2000]

        # Line numbers start at 1, so add 1 to the index
        line_number = i + 1
        result_lines.append(f"{line_number:6d}\t{line_content}")

    return "\n".join(result_lines)


@tool(description=WRITE_FILE_TOOL_DESCRIPTION)
def write_file(
file_path: str,
content: str,
state: Annotated[FilesystemState, InjectedState],
tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
files = state.get("files", {})
files[file_path] = content
return Command(
update={
"files": files,
"messages": [
ToolMessage(f"Updated file {file_path}", tool_call_id=tool_call_id)
],
}
)


@tool(description=EDIT_FILE_TOOL_DESCRIPTION)
def edit_file(
file_path: str,
old_string: str,
new_string: str,
state: Annotated[FilesystemState, InjectedState],
tool_call_id: Annotated[str, InjectedToolCallId],
replace_all: bool = False,
) -> Union[Command, str]:
"""Write to a file."""
mock_filesystem = state.get("files", {})
# Check if file exists in mock filesystem
if file_path not in mock_filesystem:
return f"Error: File '{file_path}' not found"

    # Get current file content
    content = mock_filesystem[file_path]

    # Check if old_string exists in the file
    if old_string not in content:
        return f"Error: String not found in file: '{old_string}'"

    # If not replace_all, check for uniqueness
    if not replace_all:
        occurrences = content.count(old_string)
        if occurrences > 1:
            return f"Error: String '{old_string}' appears {occurrences} times in file. Use replace_all=True to replace all instances, or provide a more specific string with surrounding context."
        elif occurrences == 0:
            return f"Error: String not found in file: '{old_string}'"

    # Perform the replacement
    if replace_all:
        new_content = content.replace(old_string, new_string)
        replacement_count = content.count(old_string)
        result_msg = f"Successfully replaced {replacement_count} instance(s) of the string in '{file_path}'"
    else:
        new_content = content.replace(
            old_string, new_string, 1
        )  # Replace only first occurrence
        result_msg = f"Successfully replaced string in '{file_path}'"

    # Update the mock filesystem
    mock_filesystem[file_path] = new_content
    return Command(
        update={
            "files": mock_filesystem,
            "messages": [ToolMessage(result_msg, tool_call_id=tool_call_id)],
        }
    )



================================================
FILE: src/deepagents/types.py
================================================
from typing import NotRequired, Union, Any
from typing_extensions import TypedDict
from langchain_core.language_models import LanguageModelLike
from langchain.agents.middleware import AgentMiddleware
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool

class SubAgent(TypedDict):
name: str
description: str
prompt: str
tools: NotRequired[list[BaseTool]]
# Optional per-subagent model: can be either a model instance OR dict settings
model: NotRequired[Union[LanguageModelLike, dict[str, Any]]]
middleware: NotRequired[list[AgentMiddleware]]


class CustomSubAgent(TypedDict):
name: str
description: str
graph: Runnable

