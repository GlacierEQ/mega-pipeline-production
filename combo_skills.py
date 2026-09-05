#!/usr/bin/env python3
"""
Combo Skills — Compound Workflow Patterns
Inspired by mega-skills combo-skills pattern.

Defines compound workflows that combine multiple skills.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ComboStatus(Enum):
    """Status of a combo skill."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SkillStep:
    """A step in a combo skill."""
    skill_id: str
    name: str
    description: str = ""
    inputs: Dict[str, str] = field(default_factory=dict)
    outputs: Dict[str, str] = field(default_factory=dict)
    timeout: int = 300
    retry: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "timeout": self.timeout,
            "retry": self.retry,
        }


@dataclass
class ComboSkill:
    """A compound workflow combining multiple skills."""
    id: str
    name: str
    description: str
    steps: List[SkillStep]
    version: str = "1.0.0"
    tags: List[str] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "version": self.version,
            "tags": self.tags,
            "artifacts": self.artifacts,
        }

    def get_step(self, skill_id: str) -> Optional[SkillStep]:
        """Get a step by skill ID."""
        for step in self.steps:
            if step.skill_id == skill_id:
                return step
        return None

    def validate(self) -> List[str]:
        """Validate the combo skill."""
        errors = []
        skill_ids = set()

        for step in self.steps:
            if step.skill_id in skill_ids:
                errors.append(f"Duplicate skill ID: {step.skill_id}")
            skill_ids.add(step.skill_id)

        return errors


class ComboRegistry:
    """Registry for combo skills."""

    def __init__(self) -> None:
        self.combos: Dict[str, ComboSkill] = {}

    def register(self, combo: ComboSkill) -> None:
        """Register a combo skill."""
        self.combos[combo.id] = combo

    def get(self, combo_id: str) -> Optional[ComboSkill]:
        """Get a combo skill by ID."""
        return self.combos.get(combo_id)

    def list_all(self) -> List[ComboSkill]:
        """List all combo skills."""
        return list(self.combos.values())

    def list_by_tag(self, tag: str) -> List[ComboSkill]:
        """List combo skills by tag."""
        return [c for c in self.combos.values() if tag in c.tags]

    def validate_all(self) -> Dict[str, List[str]]:
        """Validate all combo skills."""
        results = {}
        for combo_id, combo in self.combos.items():
            errors = combo.validate()
            if errors:
                results[combo_id] = errors
        return results


# ─── Built-in Combo Skills ───────────────────────────────────────────────────

PIPELINE_COMBO = ComboSkill(
    id="pipeline-build-test-deploy",
    name="Pipeline Build Test Deploy",
    description="Complete pipeline: build, test, deploy",
    steps=[
        SkillStep("build", "Build", "Compile and package"),
        SkillStep("test", "Test", "Run test suite"),
        SkillStep("deploy", "Deploy", "Deploy to production"),
    ],
    tags=["pipeline", "ci/cd"],
)

RESEARCH_COMBO = ComboSkill(
    id="research-analyze-synthesize",
    name="Research Analyze Synthesize",
    description="Research workflow: collect, analyze, synthesize",
    steps=[
        SkillStep("collect", "Collect", "Gather sources"),
        SkillStep("analyze", "Analyze", "Analyze data"),
        SkillStep("synthesize", "Synthesize", "Create report"),
    ],
    tags=["research", "analysis"],
)

SECURITY_COMBO = ComboSkill(
    id="security-scan-harden",
    name="Security Scan Harden",
    description="Security workflow: scan, analyze, harden",
    steps=[
        SkillStep("scan", "Scan", "Scan for vulnerabilities"),
        SkillStep("analyze", "Analyze", "Analyze findings"),
        SkillStep("harden", "Harden", "Apply security fixes"),
    ],
    tags=["security", "hardening"],
)


def register_builtins(registry: ComboRegistry) -> None:
    """Register built-in combo skills."""
    registry.register(PIPELINE_COMBO)
    registry.register(RESEARCH_COMBO)
    registry.register(SECURITY_COMBO)
