import asyncio
from fnmatch import fnmatch
from typing import Any, cast

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph, StateGraph

from src.agents import ContextSchemaType, StateSchemaType
from src.agents.deep_agent import create_deep_agent
from src.core.config import AgentConfig, LLMConfig, MCPConfig
from src.core.logging import get_logger
from src.llms.factory import LLMFactory
from src.mcp.factory import MCPFactory
from src.tools.factory import ToolFactory
from src.tools.subagents.task import SubAgent, think
from src.utils.render import render_templates

logger = get_logger(__name__)


class AgentFactory:
    def __init__(self):
        pass

    @staticmethod
    def create(
        name: str,
        tools: list[BaseTool],
        llm: BaseChatModel,
        prompt: str,
        state_schema: StateSchemaType,
        internal_tools: list[BaseTool] | None = None,
        context_schema: ContextSchemaType | None = None,
        subagents: list[SubAgent] | None = None,
    ) -> CompiledStateGraph:

        """
        Constructs a compiled agent state graph configured with the given model, tools, prompt, and schemas.
        
        Parameters:
            name: Human-readable name for the agent.
            tools: List of implementation tools available to the agent.
            llm: Chat model used by the agent for reasoning and generation.
            prompt: Rendered prompt text used to initialize the agent's behavior.
            state_schema: Schema that defines the agent's persistent state structure.
            internal_tools: Optional list of internal-only tools (not exposed externally).
            context_schema: Optional schema describing the agent's execution/context variables.
            subagents: Optional list of SubAgent instances to include as child agents.
        
        Returns:
            CompiledStateGraph: A compiled state graph representing the assembled agent.
        """
        agent = create_deep_agent(
            name=name,
            model=llm,
            tools=tools,
            internal_tools=internal_tools,
            prompt=prompt,
            state_schema=state_schema,
            context_schema=context_schema,
            subagents=subagents,
        )

        return agent


class GraphFactory:
    def __init__(
        self,
        agent_factory: AgentFactory,
        tool_factory: ToolFactory,
        mcp_factory: MCPFactory,
        llm_factory: LLMFactory,
    ):
        self.agent_factory = agent_factory
        self.tool_factory = tool_factory
        self.mcp_factory = mcp_factory
        self.llm_factory = llm_factory

    @staticmethod
    def _parse_tool_references(
        tool_refs: list[str] | None,
    ) -> tuple[list[str] | None, list[str] | None, list[str] | None]:
        if not tool_refs:
            return None, None, None

        impl_patterns = []
        mcp_patterns = []
        internal_patterns = []

        for ref in tool_refs:
            parts = ref.split(":")
            if len(parts) != 3:
                logger.warning(f"Invalid tool reference format: {ref}")
                continue

            tool_type, module_pattern, tool_pattern = parts

            if tool_type == "impl":
                impl_patterns.append(f"{module_pattern}:{tool_pattern}")
            elif tool_type == "mcp":
                mcp_patterns.append(f"{module_pattern}:{tool_pattern}")
            elif tool_type == "internal":
                internal_patterns.append(f"{module_pattern}:{tool_pattern}")
            else:
                logger.warning(f"Unknown tool type: {tool_type}")

        return (
            impl_patterns or None,
            mcp_patterns or None,
            internal_patterns or None,
        )

    @staticmethod
    def _build_tool_dict(tools: list[BaseTool]) -> dict[str, BaseTool]:
        return {tool.name: tool for tool in tools}

    @staticmethod
    def _filter_tools(
        tool_dict: dict[str, BaseTool],
        patterns: list[str] | None,
        module_map: dict[str, str],
    ) -> list[BaseTool]:
        """Filter tools by pattern with wildcard support.

        Args:
            tool_dict: Dict of all available tools keyed by name
            patterns: List of patterns (module:tool), or None to include none
            module_map: Map of tool name to module name

        Returns:
            Filtered list of tools
        """
        if not patterns:
            return []

        matched_names = set()
        for pattern in patterns:
            module_pattern, tool_pattern = pattern.split(":")
            for tool_name in tool_dict:
                module_name = module_map.get(tool_name, "")
                if fnmatch(module_name, module_pattern) and fnmatch(
                    tool_name, tool_pattern
                ):
                    matched_names.add(tool_name)

        return [tool_dict[name] for name in matched_names]

    def _create_subagent(
        self,
        subagent_config,
        impl_tool_dict: dict[str, BaseTool],
        mcp_tool_dict: dict[str, BaseTool],
        internal_tool_dict: dict[str, BaseTool],
        impl_module_map: dict[str, str],
        mcp_module_map: dict[str, str],
        internal_module_map: dict[str, str],
        template_context: dict[str, Any] | None,
    ) -> SubAgent:
        """
        Construct a SubAgent configured with its LLM, resolved tools, and a rendered prompt.
        
        Parameters:
            subagent_config: Configuration object for the subagent (must provide `llm`, `tools`, `prompt`, `name`, and `description`).
            impl_tool_dict (dict[str, BaseTool]): Mapping of implementation tool name to tool instance used to resolve implementation tools.
            mcp_tool_dict (dict[str, BaseTool]): Mapping of MCP tool name to tool instance used to resolve MCP tools.
            internal_tool_dict (dict[str, BaseTool]): Mapping of internal tool name to tool instance used to resolve internal tools.
            impl_module_map (dict[str, str]): Mapping from implementation tool name to its module identifier for pattern matching.
            mcp_module_map (dict[str, str]): Mapping from MCP tool name to its module identifier for pattern matching.
            internal_module_map (dict[str, str]): Mapping from internal tool name to its module identifier for pattern matching.
            template_context (dict[str, Any] | None): Optional context used to render the subagent's prompt templates.
        
        Returns:
            SubAgent: A SubAgent with the configured name, description, rendered prompt, created LLM, combined tools (implementation + MCP + think), and resolved internal tools.
        """
        sub_llm = self.llm_factory.create(subagent_config.llm)
        sub_impl_patterns, sub_mcp_patterns, sub_internal_patterns = (
            self._parse_tool_references(subagent_config.tools)
        )
        sub_impl_tools = self._filter_tools(
            impl_tool_dict, sub_impl_patterns, impl_module_map
        )
        sub_mcp_tools = self._filter_tools(
            mcp_tool_dict, sub_mcp_patterns, mcp_module_map
        )
        sub_internal_tools = self._filter_tools(
            internal_tool_dict, sub_internal_patterns, internal_module_map
        )
        rendered_sub_prompt = cast(
            str, render_templates(subagent_config.prompt, template_context or {})
        )
        return SubAgent(
            name=subagent_config.name,
            description=subagent_config.description,
            prompt=rendered_sub_prompt,
            llm=sub_llm,
            tools=sub_impl_tools + sub_mcp_tools + [think],
            internal_tools=sub_internal_tools,
        )

    async def create(
        self,
        config: AgentConfig,
        state_schema: StateSchemaType,
        context_schema: ContextSchemaType | None,
        mcp_config: MCPConfig,
        llm_config: LLMConfig | None = None,
        template_context: dict[str, Any] | None = None,
    ) -> StateGraph:
        """
        Builds a StateGraph for an agent based on the provided configuration and schemas.
        
        Creates and returns a configured StateGraph containing the compiled agent node, with the graph's entry and finish points set and the resolved tools cached on the builder.
        
        Parameters:
            config (AgentConfig): Agent configuration containing name, prompt, tools selection, optional subagents, and other agent settings.
            state_schema (StateSchemaType): Schema describing the agent's state shape for the StateGraph.
            context_schema (ContextSchemaType | None): Optional schema describing the agent's execution context.
            mcp_config (MCPConfig): Configuration used to create the MCP client to load MCP-provided tools.
            llm_config (LLMConfig | None): Optional LLM configuration to override the LLM specified in `config`.
            template_context (dict[str, Any] | None): Optional variables for rendering prompt templates. If this contains a `user_memory` key and the prompt does not include a `{user_memory}` placeholder, a user memory placeholder will be appended to the rendered prompt.
        
        Returns:
            StateGraph: The configured StateGraph builder containing the created agent node and cached tools.
        """
        builder = StateGraph(state_schema)
        mcp_client = await self.mcp_factory.create(mcp_config)

        all_impl_tools = self.tool_factory.get_impl_tools()
        all_internal_tools = self.tool_factory.get_internal_tools()
        all_mcp_tools = await mcp_client.get_mcp_tools()

        impl_tool_dict = self._build_tool_dict(all_impl_tools)
        internal_tool_dict = self._build_tool_dict(all_internal_tools)
        mcp_tool_dict = self._build_tool_dict(all_mcp_tools)

        impl_module_map = self.tool_factory.get_impl_module_map()
        internal_module_map = self.tool_factory.get_internal_module_map()
        mcp_module_map = mcp_client.get_mcp_module_map()

        impl_patterns, mcp_patterns, internal_patterns = self._parse_tool_references(
            config.tools
        )

        tools = self._filter_tools(mcp_tool_dict, mcp_patterns, mcp_module_map)
        tools += self._filter_tools(impl_tool_dict, impl_patterns, impl_module_map)
        internal_tools = self._filter_tools(
            internal_tool_dict, internal_patterns, internal_module_map
        )

        llm = self.llm_factory.create(llm_config or cast(LLMConfig, config.llm))

        resolved_subagents = None
        if config.subagents:
            tasks = [
                asyncio.to_thread(
                    self._create_subagent,
                    sc,
                    impl_tool_dict,
                    mcp_tool_dict,
                    internal_tool_dict,
                    impl_module_map,
                    mcp_module_map,
                    internal_module_map,
                    template_context,
                )
                for sc in config.subagents
            ]
            resolved_subagents = await asyncio.gather(*tasks)

        # Render main agent prompt with template context
        prompt_str = cast(str, config.prompt)
        template_context = template_context or {}
        if template_context.get("user_memory") and "{user_memory}" not in prompt_str:
            prompt_str = f"{prompt_str}\n\n{{user_memory}}"

        rendered_prompt = cast(str, render_templates(prompt_str, template_context))

        agent = self.agent_factory.create(
            name=config.name,
            tools=tools,
            internal_tools=internal_tools,
            llm=llm,
            prompt=rendered_prompt,
            state_schema=state_schema,
            context_schema=context_schema,
            subagents=resolved_subagents,
        )
        builder.add_node(
            config.name,
            agent,
        )

        builder.set_entry_point(config.name)
        builder.set_finish_point(config.name)
        # Store tools for cache access
        builder._tools = tools + internal_tools  # type: ignore
        return builder