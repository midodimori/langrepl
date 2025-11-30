from __future__ import annotations

import asyncio
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import TYPE_CHECKING, cast

from src.agents.deep_agent import create_deep_agent
from src.core.config import LLMConfig
from src.core.constants import (
    TOOL_CATEGORY_IMPL,
    TOOL_CATEGORY_INTERNAL,
    TOOL_CATEGORY_MCP,
)
from src.core.logging import get_logger
from src.tools.catalog.skills import get_skill
from src.tools.subagents.task import SubAgent, think

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool
    from langgraph.checkpoint.base import BaseCheckpointSaver
    from langgraph.graph.state import CompiledStateGraph

    from src.agents import ContextSchemaType, StateSchemaType
    from src.core.config import (
        AgentConfig,
        SkillsConfig,
        SubAgentConfig,
        ToolsConfig,
    )
    from src.llms.factory import LLMFactory
    from src.mcp.client import MCPClient
    from src.skills.factory import Skill, SkillFactory
    from src.tools.factory import ToolFactory

logger = get_logger(__name__)


@dataclass
class ToolResources:
    impl: dict[str, BaseTool]
    mcp: dict[str, BaseTool]
    internal: dict[str, BaseTool]
    impl_module_map: dict[str, str]
    mcp_module_map: dict[str, str]
    internal_module_map: dict[str, str]


@dataclass
class SkillResources:
    skill_dict: dict[str, Skill]
    module_map: dict[str, str]


@dataclass
class ToolSelection:
    llm_tools: list[BaseTool]
    internal_tools: list[BaseTool]
    tools_in_catalog: list[BaseTool]


@dataclass
class SkillSelection:
    skills: list[Skill]
    prompt_suffix: str
    tools: list[BaseTool]


class AgentFactory:
    def __init__(
        self,
        tool_factory: ToolFactory,
        llm_factory: LLMFactory,
        skill_factory: SkillFactory,
    ):
        self.tool_factory = tool_factory
        self.llm_factory = llm_factory
        self.skill_factory = skill_factory

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

            if tool_type == TOOL_CATEGORY_IMPL:
                impl_patterns.append(f"{module_pattern}:{tool_pattern}")
            elif tool_type == TOOL_CATEGORY_MCP:
                mcp_patterns.append(f"{module_pattern}:{tool_pattern}")
            elif tool_type == TOOL_CATEGORY_INTERNAL:
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

    def _resolve_tools(
        self,
        tools_config: ToolsConfig | None,
        tool_resources: ToolResources,
        extra_llm_tools: list[BaseTool] | None = None,
        *,
        impl_first: bool = False,
    ) -> ToolSelection:
        tool_patterns = tools_config.patterns if tools_config else None
        use_catalog = tools_config.use_catalog if tools_config else False

        impl_patterns, mcp_patterns, internal_patterns = self._parse_tool_references(
            tool_patterns
        )

        ordered_llm_tools = (
            [
                *self._filter_tools(
                    tool_resources.impl, impl_patterns, tool_resources.impl_module_map
                ),
                *self._filter_tools(
                    tool_resources.mcp, mcp_patterns, tool_resources.mcp_module_map
                ),
            ]
            if impl_first
            else [
                *self._filter_tools(
                    tool_resources.mcp, mcp_patterns, tool_resources.mcp_module_map
                ),
                *self._filter_tools(
                    tool_resources.impl, impl_patterns, tool_resources.impl_module_map
                ),
            ]
        )

        llm_tools = ordered_llm_tools
        tools_in_catalog: list[BaseTool] = []
        if use_catalog:
            tools_in_catalog = llm_tools
            llm_tools = [*self.tool_factory.get_catalog_tools()]

        if extra_llm_tools:
            llm_tools = [*llm_tools, *extra_llm_tools]

        internal_tools = self._filter_tools(
            tool_resources.internal,
            internal_patterns,
            tool_resources.internal_module_map,
        )

        return ToolSelection(
            llm_tools=llm_tools,
            internal_tools=internal_tools,
            tools_in_catalog=tools_in_catalog,
        )

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

    @staticmethod
    def _parse_skill_references(skill_refs: list[str] | None) -> list[str] | None:
        if not skill_refs:
            return None

        skill_patterns = []
        for ref in skill_refs:
            parts = ref.split(":")
            if len(parts) != 2:
                logger.warning(f"Invalid skill reference format: {ref}")
                continue

            category_pattern, skill_pattern = parts
            skill_patterns.append(f"{category_pattern}:{skill_pattern}")

        return skill_patterns or None

    @staticmethod
    def _build_skill_dict(
        skills: dict[str, dict[str, Skill]],
    ) -> dict[str, Skill]:
        skill_dict = {}
        for category, category_skills in skills.items():
            for name, skill in category_skills.items():
                # Use composite key to handle same skill name in different categories
                composite_key = f"{category}:{name}"
                skill_dict[composite_key] = skill
        return skill_dict

    @staticmethod
    def _filter_skills(
        skill_dict: dict[str, Skill],
        patterns: list[str] | None,
        module_map: dict[str, str],
    ) -> list[Skill]:
        if not patterns:
            return []

        matched_keys = set()
        for pattern in patterns:
            category_pattern, skill_pattern = pattern.split(":")
            for composite_key in skill_dict:
                # composite_key format: "category:name"
                category_name = module_map.get(composite_key, "")
                # Extract skill name from composite key
                skill_name = (
                    composite_key.split(":", 1)[1]
                    if ":" in composite_key
                    else composite_key
                )
                if fnmatch(category_name, category_pattern) and fnmatch(
                    skill_name, skill_pattern
                ):
                    matched_keys.add(composite_key)

        return [skill_dict[key] for key in matched_keys]

    def _resolve_skills(
        self,
        skills_config: SkillsConfig | None,
        skill_resources: SkillResources,
    ) -> SkillSelection:
        skill_patterns = skills_config.patterns if skills_config else None
        use_catalog = skills_config.use_catalog if skills_config else False

        parsed_patterns = self._parse_skill_references(skill_patterns)
        skills = self._filter_skills(
            skill_resources.skill_dict, parsed_patterns, skill_resources.module_map
        )

        prompt_suffix = ""
        tools: list[BaseTool] = []
        if skills:
            prompt_suffix = self._build_skills_text(skills, use_catalog)
            tools = self._get_skill_tools(use_catalog)

        return SkillSelection(skills=skills, prompt_suffix=prompt_suffix, tools=tools)

    def _get_skill_tools(self, use_catalog: bool) -> list[BaseTool]:
        """Get skill-related tools based on catalog mode."""
        if use_catalog:
            return self.tool_factory.get_skill_catalog_tools()
        return [get_skill]

    @staticmethod
    def _build_skills_text(skills: list[Skill], use_catalog: bool = False) -> str:
        """Build skills documentation text for prompt injection."""
        text = "\n\n# Available Skills\n\n"

        if use_catalog:
            text += "Skills are available to help with many types of tasks including coding, debugging, testing, documentation, analysis, and more. "
            text += "Use `fetch_skills` to search for relevant skills or to browse all available skills. "
            text += "Check for applicable skills at the start of tasks - they can significantly improve your responses.\n"
        else:
            text += "When users ask you to perform tasks, check if any of the available skills below can help complete the task more effectively.\n\n"
            for skill in skills:
                text += f"- **{skill.category}/{skill.name}**: {skill.description}\n"

        return text

    def _create_subagent(
        self,
        subagent_config: SubAgentConfig,
        tool_resources: ToolResources,
        skill_resources: SkillResources,
    ) -> SubAgent:
        tool_selection = self._resolve_tools(
            subagent_config.tools,
            tool_resources,
            extra_llm_tools=[think],
            impl_first=True,
        )

        skill_selection = self._resolve_skills(
            subagent_config.skills,
            skill_resources,
        )

        sub_prompt_template = cast(str, subagent_config.prompt)
        if skill_selection.prompt_suffix:
            sub_prompt_template = (
                f"{sub_prompt_template}{skill_selection.prompt_suffix}"
            )

        sub_llm_tools = [*tool_selection.llm_tools, *skill_selection.tools]

        return SubAgent(
            config=subagent_config,
            prompt=sub_prompt_template,
            tools=sub_llm_tools,
            internal_tools=tool_selection.internal_tools,
            tools_in_catalog=tool_selection.tools_in_catalog,
            skills=skill_selection.skills,
        )

    async def create(
        self,
        config: AgentConfig,
        state_schema: StateSchemaType,
        context_schema: ContextSchemaType | None,
        mcp_client: MCPClient,
        skills_dir: Path,
        checkpointer: BaseCheckpointSaver | None = None,
        llm_config: LLMConfig | None = None,
    ) -> CompiledStateGraph:
        """Create a compiled graph with optional checkpointer support.

        Args:
            config: Agent configuration including checkpointer settings
            state_schema: State schema for the graph
            context_schema: Optional context schema for the graph
            mcp_client: MCP client for tool loading
            skills_dir: Skills directory path
            checkpointer: Optional checkpoint saver
            llm_config: Optional LLM configuration to override the one in config

        Returns:
            CompiledStateGraph: The state graph
        """

        tool_resources = ToolResources(
            impl=self._build_tool_dict(self.tool_factory.get_impl_tools()),
            mcp=self._build_tool_dict(await mcp_client.get_mcp_tools()),
            internal=self._build_tool_dict(self.tool_factory.get_internal_tools()),
            impl_module_map=self.tool_factory.get_impl_module_map(),
            mcp_module_map=mcp_client.get_mcp_module_map(),
            internal_module_map=self.tool_factory.get_internal_module_map(),
        )

        skills = await self.skill_factory.load_skills(skills_dir)

        skill_resources = SkillResources(
            skill_dict=self._build_skill_dict(skills),
            module_map=self.skill_factory.get_module_map(),
        )

        tool_selection = self._resolve_tools(config.tools, tool_resources)
        skill_selection = self._resolve_skills(config.skills, skill_resources)

        resolved_subagents = None
        if config.subagents:
            tasks = [
                asyncio.to_thread(
                    self._create_subagent,
                    sc,
                    tool_resources,
                    skill_resources,
                )
                for sc in config.subagents
            ]
            resolved_subagents = await asyncio.gather(*tasks)

        prompt_template = cast(str, config.prompt)
        if "{user_memory}" not in prompt_template:
            prompt_template = f"{prompt_template}\n\n{{user_memory}}"

        if skill_selection.prompt_suffix:
            prompt_template = f"{prompt_template}{skill_selection.prompt_suffix}"

        llm_tools = [*tool_selection.llm_tools, *skill_selection.tools]
        internal_tools = tool_selection.internal_tools
        tools_in_catalog = tool_selection.tools_in_catalog

        agent = create_deep_agent(
            name=config.name,
            tools=llm_tools,
            internal_tools=internal_tools,
            llm_config=llm_config or cast(LLMConfig, config.llm),
            prompt=prompt_template,
            state_schema=state_schema,
            context_schema=context_schema,
            checkpointer=checkpointer,
            subagents=resolved_subagents,
            model_provider=self.llm_factory.create,
        )
        agent._llm_tools = llm_tools + internal_tools  # type: ignore
        agent._tools_in_catalog = tools_in_catalog  # type: ignore
        agent._agent_skills = skill_selection.skills  # type: ignore
        return agent
