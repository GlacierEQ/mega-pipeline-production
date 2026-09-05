#!/usr/bin/env python3
"""
Tests for Combo Skills.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from combo_skills import (
    ComboSkill, SkillStep, ComboRegistry, ComboStatus,
    PIPELINE_COMBO, RESEARCH_COMBO, SECURITY_COMBO,
    register_builtins,
)


class TestComboSkill:
    def test_create(self):
        combo = ComboSkill(
            id="test",
            name="Test Combo",
            description="A test combo",
            steps=[SkillStep("s1", "Step 1")],
        )
        assert combo.id == "test"
        assert len(combo.steps) == 1

    def test_get_step(self):
        combo = ComboSkill(
            id="test",
            name="Test Combo",
            description="A test combo",
            steps=[
                SkillStep("s1", "Step 1"),
                SkillStep("s2", "Step 2"),
            ],
        )
        step = combo.get_step("s2")
        assert step is not None
        assert step.name == "Step 2"

    def test_validate(self):
        combo = ComboSkill(
            id="test",
            name="Test Combo",
            description="A test combo",
            steps=[
                SkillStep("s1", "Step 1"),
                SkillStep("s1", "Step 1 Duplicate"),
            ],
        )
        errors = combo.validate()
        assert len(errors) > 0

    def test_to_dict(self):
        combo = ComboSkill(
            id="test",
            name="Test Combo",
            description="A test combo",
            steps=[SkillStep("s1", "Step 1")],
        )
        d = combo.to_dict()
        assert d["id"] == "test"
        assert len(d["steps"]) == 1


class TestComboRegistry:
    def test_register(self):
        registry = ComboRegistry()
        combo = ComboSkill(
            id="test",
            name="Test",
            description="Test",
            steps=[],
        )
        registry.register(combo)
        assert len(registry.list_all()) == 1

    def test_get(self):
        registry = ComboRegistry()
        combo = ComboSkill(
            id="test",
            name="Test",
            description="Test",
            steps=[],
        )
        registry.register(combo)
        result = registry.get("test")
        assert result is not None

    def test_list_by_tag(self):
        registry = ComboRegistry()
        combo = ComboSkill(
            id="test",
            name="Test",
            description="Test",
            steps=[],
            tags=["pipeline"],
        )
        registry.register(combo)
        results = registry.list_by_tag("pipeline")
        assert len(results) == 1


class TestBuiltins:
    def test_register_builtins(self):
        registry = ComboRegistry()
        register_builtins(registry)
        assert len(registry.list_all()) == 3

    def test_pipeline_combo(self):
        assert PIPELINE_COMBO.id == "pipeline-build-test-deploy"
        assert len(PIPELINE_COMBO.steps) == 3


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
