import asyncio
from fnmatch import fnmatch
from typing import Any, cast

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

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
        context_schema: ContextSchemaType | None = None,
        checkpointer: BaseCheckpointSaver | None = None,
        internal_tools: list[BaseTool] | None = None,
        subagents: list[SubAgent] | None = None,
    ) -> CompiledStateGraph:

        agent = create_deep_agent(
            name=name,
            model=llm,
            tools=tools,
            internal_tools=internal_tools,
            prompt=prompt,
            state_schema=state_schema,
            context_schema=context_schema,
            checkpointer=checkpointer,
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
        checkpointer: BaseCheckpointSaver | None = None,
        llm_config: LLMConfig | None = None,
        template_context: dict[str, Any] | None = None,
    ) -> CompiledStateGraph:
        """Create a compiled graph with optional checkpointer support.

        Args:
            config: Agent configuration including checkpointer settings
            state_schema: State schema for the graph
            context_schema: Optional context schema for the graph
            mcp_config: MCP configuration for tool loading
            checkpointer: Optional checkpoint saver
            llm_config: Optional LLM configuration to override the one in config
            template_context: Optional template variables for prompt rendering

        Returns:
            CompiledStateGraph: The state graph
        """
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
            checkpointer=checkpointer,
            subagents=resolved_subagents,
        )
        # Store tools for cache access
        agent._tools = tools + internal_tools  # type: ignore
        return agent
