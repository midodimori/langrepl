import json
import re

from langchain.tools import ToolRuntime, tool
from langchain_core.tools import ToolException

from src.agents.context import AgentContext


@tool
async def fetch_skills(
    runtime: ToolRuntime[AgentContext], pattern: str | None = None
) -> str:
    """Discover and search for available skills in the catalog.

    When users ask you to perform tasks, check if any of the available skills can help
    complete the task more effectively. Skills provide specialized capabilities and domain knowledge.

    Skills are specialized knowledge packages that provide workflows, domain expertise,
    and tool integrations. Use this to find skills relevant to your current task.

    WITHOUT pattern: Returns ALL available skills (use for browsing/exploring)
    WITH pattern: Returns ONLY matching skills (use when you know what you're looking for)

    The pattern searches skill names AND descriptions using case-insensitive regex.

    Args:
        pattern: Optional regex pattern to filter skills. Common patterns:
            - Simple keyword: "python", "code", "review"
            - Multiple keywords: "test|debug"
            - Category: "general|coding"

    Returns:
        JSON array of skill objects with: category, name, description.
        Returns empty array if no matches found.

    When to use:
        - Starting a task: fetch_skills("keyword") to find relevant skills
        - Exploring capabilities: fetch_skills() to see all available skills
        - Looking for domain expertise: fetch_skills("python") to find Python-related skills

    Example workflow:
    1. fetch_skills("code") - find code-related skills
    2. get_skill("coding", "python-best-practices") - read the full skill content
    3. Apply the skill's guidance to your task

    Examples:
        fetch_skills() - list all available skills
        fetch_skills("python") - find Python-related skills
        fetch_skills("code|review") - find skills for coding or reviewing
    """
    skills = runtime.context.skill_catalog

    if not skills:
        return json.dumps([])

    if pattern is None:
        result = [
            {
                "category": skill.category,
                "name": skill.name,
                "description": skill.description,
            }
            for skill in skills
        ]
        return json.dumps(result, indent=2)

    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        raise ToolException(f"Invalid regex pattern: {e}") from e

    matches = []
    for skill in skills:
        if (
            regex.search(skill.name)
            or regex.search(skill.category)
            or regex.search(skill.description)
        ):
            matches.append(
                {
                    "category": skill.category,
                    "name": skill.name,
                    "description": skill.description,
                }
            )

    return json.dumps(matches, indent=2)


fetch_skills.metadata = {"approval_config": {"always_approve": True}}


@tool
async def get_skill(
    category: str, name: str, runtime: ToolRuntime[AgentContext]
) -> str:
    """Read the full content of a specific skill.

    Use this after fetch_skills() when you've identified a skill you want to use.
    Returns the complete SKILL.md content including all instructions, workflows,
    and guidance.

    Args:
        category: Category of the skill (from fetch_skills() output)
        name: Name of the skill (from fetch_skills() output)

    Returns:
        Complete SKILL.md content with instructions and guidance
    """
    skills = runtime.context.skill_catalog
    skill = next((s for s in skills if s.category == category and s.name == name), None)

    if not skill:
        raise ToolException(f"Skill '{category}/{name}' not found")

    content = skill.read_content()
    if not content:
        raise ToolException(f"Failed to read skill '{category}/{name}'")

    return content


get_skill.metadata = {"approval_config": {"always_approve": True}}


SKILL_CATALOG_TOOLS = [fetch_skills, get_skill]
