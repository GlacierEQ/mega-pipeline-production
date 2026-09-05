#!/usr/bin/env python3
"""
Tests for Combo Skills — Compound Workflow Patterns.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from combo_skills import (
    ComboSkill, SkillStep, ComboRegistry, ComboStatus,
    PIPELINE_COMBO, RESEARCH_COMBO, SECURITY_COMBO,
    register_builtins,
)


class TestSkillStep:
    def test_create(self):
        step = SkillStep(skill_id="s1", name="Step 1", description="A step")
        assert step.skill_id == "s1"
        assert step.name == "Step 1"

    def test_to_dict(self):
        step = SkillStep(skill_id="s1", name="Step 1")
        d = step.to_dict()
        assert d["skill_id"] == "s1"
        assert d["name"] == "Step 1"

    def test_defaults(self):
        step = SkillStep(skill_id="s1", name="Step 1")
        assert step.description == ""
        assert step.inputs == {}
        assert step.outputs == {}
        assert step.timeout == 300
        assert step.retry == 0


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
            name="Test",
            description="Test",
            steps=[
                SkillStep("s1", "Step 1"),
                SkillStep("s2", "Step 2"),
            ],
        )
        step = combo.get_step("s2")
        assert step is not None
        assert step.name == "Step 2"

    def test_get_step_not_found(self):
        combo = ComboSkill(
            id="test",
            name="Test",
            description="Test",
            steps=[],
        )
        step = combo.get_step("missing")
        assert step is None

    def test_validate_valid(self):
        combo = ComboSkill(
            id="test",
            name="Test",
            description="Test",
            steps=[
                SkillStep("s1", "Step 1"),
                SkillStep("s2", "Step 2"),
            ],
        )
        errors = combo.validate()
        assert len(errors) == 0

    def test_validate_duplicate(self):
        combo = ComboSkill(
            id="test",
            name="Test",
            description="Test",
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
            name="Test",
            description="Test",
            steps=[SkillStep("s1", "Step 1")],
            tags=["tag1"],
        )
        d = combo.to_dict()
        assert d["id"] == "test"
        assert len(d["steps"]) == 1
        assert "tag1" in d["tags"]


class TestComboRegistry:
    def test_register(self):
        registry = ComboRegistry()
        combo = ComboSkill(id="test", name="Test", description="Test", steps=[])
        registry.register(combo)
        assert len(registry.list_all()) == 1

    def test_get(self):
        registry = ComboRegistry()
        combo = ComboSkill(id="test", name="Test", description="Test", steps=[])
        registry.register(combo)
        result = registry.get("test")
        assert result is not None

    def test_get_not_found(self):
        registry = ComboRegistry()
        result = registry.get("missing")
        assert result is None

    def test_list_by_tag(self):
        registry = ComboRegistry()
        combo = ComboSkill(id="test", name="Test", description="Test", steps=[], tags=["pipeline"])
        registry.register(combo)
        results = registry.list_by_tag("pipeline")
        assert len(results) == 1

    def test_list_by_tag_empty(self):
        registry = ComboRegistry()
        results = registry.list_by_tag("missing")
        assert len(results) == 0

    def test_validate_all(self):
        registry = ComboRegistry()
        combo = ComboSkill(id="test", name="Test", description="Test", steps=[])
        registry.register(combo)
        results = registry.validate_all()
        assert len(results) == 0


class TestBuiltins:
    def test_register_builtins(self):
        registry = ComboRegistry()
        register_builtins(registry)
        assert len(registry.list_all()) == 3

    def test_pipeline_combo(self):
        assert PIPELINE_COMBO.id == "pipeline-build-test-deploy"
        assert len(PIPELINE_COMBO.steps) == 3

    def test_research_combo(self):
        assert RESEARCH_COMBO.id == "research-analyze-synthesize"
        assert len(RESEARCH_COMBO.steps) == 3

    def test_security_combo(self):
        assert SECURITY_COMBO.id == "security-scan-harden"
        assert len(SECURITY_COMBO.steps) == 3


class TestComboStatus:
    def test_values(self):
        assert ComboStatus.PENDING.value == "pending"
        assert ComboStatus.RUNNING.value == "running"
        assert ComboStatus.COMPLETED.value == "completed"
        assert ComboStatus.FAILED.value == "failed"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
