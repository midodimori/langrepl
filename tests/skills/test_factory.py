"""Tests for skill factory."""

import pytest

from src.skills.factory import Skill, SkillFactory


class TestSkill:
    """Tests for Skill class."""

    def test_read_content(self, temp_dir):
        """Test that read_content returns file content."""
        skill_path = temp_dir / "test.md"
        skill_path.write_text("test content")

        skill = Skill(
            name="test",
            description="test description",
            category="test",
            path=skill_path,
        )

        assert skill.read_content() == "test content"

    def test_read_content_missing_file(self, temp_dir):
        """Test that read_content handles missing file."""
        skill_path = temp_dir / "missing.md"

        skill = Skill(
            name="test",
            description="test description",
            category="test",
            path=skill_path,
        )

        assert skill.read_content() == ""

    @pytest.mark.asyncio
    async def test_from_file_valid(self, temp_dir):
        """Test that from_file parses valid skill file."""
        skill_path = temp_dir / "SKILL.md"
        skill_path.write_text(
            """---
name: test-skill
description: Test skill description
allowed_tools:
  - tool1
  - tool2
---

# Test Skill

Content here.
"""
        )

        skill = await Skill.from_file(skill_path, "test-category")

        assert skill is not None
        assert skill.name == "test-skill"
        assert skill.description == "Test skill description"
        assert skill.category == "test-category"
        assert skill.path == skill_path
        assert skill.allowed_tools == ["tool1", "tool2"]

    @pytest.mark.asyncio
    async def test_from_file_no_frontmatter(self, temp_dir):
        """Test that from_file returns None for file without frontmatter."""
        skill_path = temp_dir / "SKILL.md"
        skill_path.write_text("# Test Skill\n\nNo frontmatter here.")

        skill = await Skill.from_file(skill_path, "test-category")

        assert skill is None

    @pytest.mark.asyncio
    async def test_from_file_no_name(self, temp_dir):
        """Test that from_file returns None when name is missing."""
        skill_path = temp_dir / "SKILL.md"
        skill_path.write_text("---\ndescription: Test\n---\n\nContent")

        skill = await Skill.from_file(skill_path, "test-category")

        assert skill is None

    @pytest.mark.asyncio
    async def test_from_file_minimal(self, temp_dir):
        """Test that from_file works with minimal frontmatter."""
        skill_path = temp_dir / "SKILL.md"
        skill_path.write_text("---\nname: minimal-skill\n---\n\nContent")

        skill = await Skill.from_file(skill_path, "test-category")

        assert skill is not None
        assert skill.name == "minimal-skill"
        assert skill.description == ""
        assert skill.allowed_tools is None


class TestSkillFactory:
    """Tests for SkillFactory class."""

    @pytest.mark.asyncio
    async def test_load_skills_empty_dir(self, temp_dir):
        """Test that load_skills returns empty dict for empty directory."""
        factory = SkillFactory()

        skills = await factory.load_skills(temp_dir)

        assert skills == {}

    @pytest.mark.asyncio
    async def test_load_skills_missing_dir(self, temp_dir):
        """Test that load_skills returns empty dict for missing directory."""
        factory = SkillFactory()

        skills = await factory.load_skills(temp_dir / "missing")

        assert skills == {}

    @pytest.mark.asyncio
    async def test_load_skills_single_skill(self, temp_dir):
        """Test that load_skills loads a single skill."""
        category_dir = temp_dir / "category1"
        skill_dir = category_dir / "skill1"
        skill_dir.mkdir(parents=True)

        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(
            "---\nname: skill1\ndescription: Test skill\n---\n\nContent"
        )

        factory = SkillFactory()
        skills = await factory.load_skills(temp_dir)

        assert "category1" in skills
        assert "skill1" in skills["category1"]
        assert skills["category1"]["skill1"].name == "skill1"
        assert skills["category1"]["skill1"].category == "category1"

    @pytest.mark.asyncio
    async def test_load_skills_multiple_categories(self, temp_dir):
        """Test that load_skills loads skills from multiple categories."""
        for cat in ["cat1", "cat2"]:
            for skill_num in [1, 2]:
                skill_dir = temp_dir / cat / f"skill{skill_num}"
                skill_dir.mkdir(parents=True)
                (skill_dir / "SKILL.md").write_text(
                    f"---\nname: skill{skill_num}\n---\n\nContent"
                )

        factory = SkillFactory()
        skills = await factory.load_skills(temp_dir)

        assert len(skills) == 2
        assert "cat1" in skills
        assert "cat2" in skills
        assert len(skills["cat1"]) == 2
        assert len(skills["cat2"]) == 2

    @pytest.mark.asyncio
    async def test_load_skills_skips_files_in_category_dir(self, temp_dir):
        """Test that load_skills skips non-directory files in category dir."""
        category_dir = temp_dir / "category1"
        category_dir.mkdir()
        (category_dir / "file.txt").write_text("not a skill")

        skill_dir = category_dir / "skill1"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: skill1\n---\n\nContent")

        factory = SkillFactory()
        skills = await factory.load_skills(temp_dir)

        assert len(skills["category1"]) == 1

    @pytest.mark.asyncio
    async def test_load_skills_skips_missing_skill_md(self, temp_dir):
        """Test that load_skills skips directories without SKILL.md."""
        category_dir = temp_dir / "category1"
        skill_dir = category_dir / "skill1"
        skill_dir.mkdir(parents=True)

        factory = SkillFactory()
        skills = await factory.load_skills(temp_dir)

        assert "category1" in skills
        assert len(skills["category1"]) == 0

    @pytest.mark.asyncio
    async def test_load_skills_skips_invalid_skill(self, temp_dir):
        """Test that load_skills skips invalid skill files."""
        category_dir = temp_dir / "category1"
        skill_dir = category_dir / "skill1"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("Invalid content")

        factory = SkillFactory()
        skills = await factory.load_skills(temp_dir)

        assert "category1" in skills
        assert len(skills["category1"]) == 0

    @pytest.mark.asyncio
    async def test_get_module_map(self, temp_dir):
        """Test that get_module_map returns correct mapping with composite keys."""
        for cat in ["cat1", "cat2"]:
            skill_dir = temp_dir / cat / "skill1"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("---\nname: skill1\n---\n\nContent")

        factory = SkillFactory()
        await factory.load_skills(temp_dir)

        module_map = factory.get_module_map()

        # Module map now uses composite keys (category:name)
        assert "cat1:skill1" in module_map
        assert "cat2:skill1" in module_map
        assert module_map["cat1:skill1"] == "cat1"
        assert module_map["cat2:skill1"] == "cat2"

    @pytest.mark.asyncio
    async def test_get_all_skills(self, temp_dir):
        """Test that get_all_skills returns all loaded skills."""
        skill_dir = temp_dir / "cat1" / "skill1"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: skill1\n---\n\nContent")

        factory = SkillFactory()
        await factory.load_skills(temp_dir)

        all_skills = factory.get_all_skills()

        assert "cat1" in all_skills
        assert "skill1" in all_skills["cat1"]

    @pytest.mark.asyncio
    async def test_get_skill(self, temp_dir):
        """Test that get_skill returns specific skill."""
        skill_dir = temp_dir / "cat1" / "skill1"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: skill1\n---\n\nContent")

        factory = SkillFactory()
        await factory.load_skills(temp_dir)

        skill = factory.get_skill("cat1", "skill1")

        assert skill is not None
        assert skill.name == "skill1"
        assert skill.category == "cat1"

    @pytest.mark.asyncio
    async def test_get_skill_not_found(self, temp_dir):
        """Test that get_skill returns None for missing skill."""
        factory = SkillFactory()
        await factory.load_skills(temp_dir)

        skill = factory.get_skill("missing", "skill")

        assert skill is None
