import asyncio
from fnmatch import fnmatch
from pathlib import Path
from typing import cast

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from src.agents import ContextSchemaType, StateSchemaType
from src.agents.deep_agent import create_deep_agent
from src.core.config import AgentConfig, LLMConfig, MCPConfig, SubAgentConfig
from src.core.constants import (
    TOOL_CATEGORY_IMPL,
    TOOL_CATEGORY_INTERNAL,
    TOOL_CATEGORY_MCP,
)
from src.core.logging import get_logger
from src.llms.factory import LLMFactory
from src.mcp.factory import MCPFactory
from src.skills.factory import Skill, SkillFactory
from src.tools.catalog.skills import get_skill
from src.tools.factory import ToolFactory
from src.tools.subagents.task import SubAgent, think

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
        skill_factory: SkillFactory,
    ):
        self.agent_factory = agent_factory
        self.tool_factory = tool_factory
        self.mcp_factory = mcp_factory
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
        impl_tool_dict: dict[str, BaseTool],
        mcp_tool_dict: dict[str, BaseTool],
        internal_tool_dict: dict[str, BaseTool],
        impl_module_map: dict[str, str],
        mcp_module_map: dict[str, str],
        internal_module_map: dict[str, str],
        skill_dict: dict[str, Skill],
        skill_module_map: dict[str, str],
    ) -> SubAgent:
        sub_llm = self.llm_factory.create(subagent_config.llm)
        sub_tool_patterns = (
            subagent_config.tools.patterns if subagent_config.tools else None
        )
        sub_impl_patterns, sub_mcp_patterns, sub_internal_patterns = (
            self._parse_tool_references(sub_tool_patterns)
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

        use_catalog = (
            subagent_config.tools.use_catalog if subagent_config.tools else False
        )
        sub_llm_tools = sub_impl_tools + sub_mcp_tools + [think]
        tools_in_catalog = []
        if use_catalog:
            tools_in_catalog = sub_impl_tools + sub_mcp_tools
            sub_llm_tools = [*self.tool_factory.get_catalog_tools(), think]

        sub_skill_patterns = (
            subagent_config.skills.patterns if subagent_config.skills else None
        )
        use_skill_catalog = (
            subagent_config.skills.use_catalog if subagent_config.skills else False
        )
        sub_skill_patterns_parsed = self._parse_skill_references(sub_skill_patterns)
        sub_skills = self._filter_skills(
            skill_dict, sub_skill_patterns_parsed, skill_module_map
        )
        sub_prompt_template = cast(str, subagent_config.prompt)

        if sub_skills:
            sub_llm_tools.extend(self._get_skill_tools(use_skill_catalog))
            sub_prompt_template = f"{sub_prompt_template}{self._build_skills_text(sub_skills, use_skill_catalog)}"

        return SubAgent(
            config=subagent_config,
            prompt=sub_prompt_template,
            llm=sub_llm,
            tools=sub_llm_tools,
            internal_tools=sub_internal_tools,
            tools_in_catalog=tools_in_catalog,
            skills=sub_skills,
        )

    async def create(
        self,
        config: AgentConfig,
        state_schema: StateSchemaType,
        context_schema: ContextSchemaType | None,
        mcp_config: MCPConfig,
        checkpointer: BaseCheckpointSaver | None = None,
        llm_config: LLMConfig | None = None,
        skills_dir: Path | None = None,
    ) -> CompiledStateGraph:
        """Create a compiled graph with optional checkpointer support.

        Args:
            config: Agent configuration including checkpointer settings
            state_schema: State schema for the graph
            context_schema: Optional context schema for the graph
            mcp_config: MCP configuration for tool loading
            checkpointer: Optional checkpoint saver
            llm_config: Optional LLM configuration to override the one in config
            skills_dir: Optional path to skills directory

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

        tool_patterns = config.tools.patterns if config.tools else None
        use_catalog = config.tools.use_catalog if config.tools else False

        impl_patterns, mcp_patterns, internal_patterns = self._parse_tool_references(
            tool_patterns
        )

        llm_tools = self._filter_tools(mcp_tool_dict, mcp_patterns, mcp_module_map)
        llm_tools += self._filter_tools(impl_tool_dict, impl_patterns, impl_module_map)
        tools_in_catalog = []
        if use_catalog:
            tools_in_catalog = llm_tools
            llm_tools = self.tool_factory.get_catalog_tools()

        internal_tools = self._filter_tools(
            internal_tool_dict, internal_patterns, internal_module_map
        )

        llm = self.llm_factory.create(llm_config or cast(LLMConfig, config.llm))

        skill_patterns = config.skills.patterns if config.skills else None
        use_skill_catalog = config.skills.use_catalog if config.skills else False

        all_skills = {}
        if skills_dir:
            all_skills = self.skill_factory.load_skills(skills_dir)
        skill_dict = self._build_skill_dict(all_skills)
        skill_module_map = self.skill_factory.get_module_map()
        skill_patterns_parsed = self._parse_skill_references(skill_patterns)

        skills = self._filter_skills(
            skill_dict, skill_patterns_parsed, skill_module_map
        )

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
                    skill_dict,
                    skill_module_map,
                )
                for sc in config.subagents
            ]
            resolved_subagents = await asyncio.gather(*tasks)

        prompt_template = cast(str, config.prompt)
        if "{user_memory}" not in prompt_template:
            prompt_template = f"{prompt_template}\n\n{{user_memory}}"

        if skills:
            llm_tools.extend(self._get_skill_tools(use_skill_catalog))
            prompt_template = (
                f"{prompt_template}{self._build_skills_text(skills, use_skill_catalog)}"
            )

        agent = self.agent_factory.create(
            name=config.name,
            tools=llm_tools,
            internal_tools=internal_tools,
            llm=llm,
            prompt=prompt_template,
            state_schema=state_schema,
            context_schema=context_schema,
            checkpointer=checkpointer,
            subagents=resolved_subagents,
        )
        agent._llm_tools = llm_tools + internal_tools  # type: ignore
        agent._tools_in_catalog = tools_in_catalog  # type: ignore
        agent._agent_skills = skills  # type: ignore
        return agent
