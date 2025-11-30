import asyncio
import re
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class Skill(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    category: str
    path: Path
    allowed_tools: list[str] | None = Field(default=None)

    def read_content(self) -> str:
        try:
            return self.path.read_text()
        except Exception:
            return ""

    @classmethod
    async def from_file(cls, skill_md: Path, category: str) -> "Skill | None":
        try:
            content = await asyncio.to_thread(skill_md.read_text)
            frontmatter_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
            if not frontmatter_match:
                return None

            frontmatter = yaml.safe_load(frontmatter_match.group(1))
            if not frontmatter or "name" not in frontmatter:
                return None

            return cls(
                name=frontmatter["name"],
                description=frontmatter.get("description", ""),
                category=category,
                path=skill_md,
                allowed_tools=frontmatter.get("allowed_tools"),
            )
        except Exception:
            return None


class SkillFactory:
    def __init__(self):
        self._skills: dict[str, dict[str, Skill]] = {}
        self._module_map: dict[str, str] = {}

    async def load_skills(self, skills_dir: Path) -> dict[str, dict[str, Skill]]:
        if not await asyncio.to_thread(skills_dir.exists):
            self._skills = {}
            self._module_map = {}
            return {}

        skills: dict[str, dict[str, Skill]] = {}
        module_map: dict[str, str] = {}

        category_dirs = await asyncio.to_thread(lambda: list(skills_dir.iterdir()))
        for category_dir in category_dirs:
            if not category_dir.is_dir():
                continue

            category_name = category_dir.name
            skills[category_name] = {}

            skill_dirs = await asyncio.to_thread(lambda: list(category_dir.iterdir()))
            for skill_dir in skill_dirs:
                if not skill_dir.is_dir():
                    continue

                skill_md = skill_dir / "SKILL.md"
                if not await asyncio.to_thread(skill_md.exists):
                    continue

                skill = await Skill.from_file(skill_md, category_name)
                if skill:
                    skills[category_name][skill.name] = skill
                    # Use composite key to handle same skill name in different categories
                    composite_key = f"{category_name}:{skill.name}"
                    module_map[composite_key] = category_name

        self._skills = skills
        self._module_map = module_map
        return skills

    def get_module_map(self) -> dict[str, str]:
        return self._module_map

    def get_all_skills(self) -> dict[str, dict[str, Skill]]:
        return self._skills

    def get_skill(self, category: str, name: str) -> Skill | None:
        return self._skills.get(category, {}).get(name)
