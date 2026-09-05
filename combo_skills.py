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
        """Register a combo skill.
        
        Raises:
            ValueError: If combo_id already exists.
        """
        if combo.id in self.combos:
            raise ValueError(f"Combo skill {combo.id} already registered")
        self.combos[combo.id] = combo

    def get(self, combo_id: str) -> Optional[ComboSkill]:
        """Get a combo skill by ID.
        
        Returns None if not found.
        """
        return self.combos.get(combo_id)

    def list_all(self) -> List[ComboSkill]:
        """List all combo skills."""
        return list(self.combos.values())

    def list_by_tag(self, tag: str) -> List[ComboSkill]:
        """List combo skills by tag."""
        return [c for c in self.combos.values() if tag in c.tags]

    def validate_all(self) -> Dict[str, List[str]]:
        """Validate all combo skills.
        
        Returns dict of combo_id -> list of errors.
        Also checks for circular dependencies between steps.
        """
        results: Dict[str, List[str]] = {}
        for combo_id, combo in self.combos.items():
            try:
                errors = combo.validate()
                # Check for circular dependencies
                cycle_errors = self._check_cycles(combo)
                errors.extend(cycle_errors)
                if errors:
                    results[combo_id] = errors
            except Exception as e:
                results[combo_id] = [f"Validation error: {e}"]
        return results

    def _check_cycles(self, combo: ComboSkill) -> List[str]:
        """Check for circular dependencies in combo steps."""
        errors: List[str] = []
        skill_ids = {step.skill_id for step in combo.steps}

        # Build adjacency list
        adj: Dict[str, Set[str]] = {step.skill_id: set() for step in combo.steps}
        for step in combo.steps:
            for input_skill in step.inputs.values():
                if input_skill in skill_ids and input_skill != step.skill_id:
                    adj[step.skill_id].add(input_skill)

        # DFS cycle detection
        visited = set()
        rec_stack = set()

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.remove(node)
            return False

        for skill_id in skill_ids:
            if skill_id not in visited:
                if dfs(skill_id):
                    errors.append(f"Circular dependency detected in {combo.id}")
                    break

        return errors

    def get_execution_order(self, combo_id: str) -> List[str]:
        """Get the optimal execution order for a combo skill's steps.
        
        Uses topological sort to order steps by their input dependencies.
        Returns step IDs in execution order.
        
        Raises:
            ValueError: If combo_id not found or has circular dependencies.
        """
        combo = self.combos.get(combo_id)
        if not combo:
            raise ValueError(f"Combo skill {combo_id} not found")

        # Build adjacency list and in-degree count
        skill_ids = {step.skill_id for step in combo.steps}
        adj: Dict[str, Set[str]] = {sid: set() for sid in skill_ids}
        in_degree: Dict[str, int] = {sid: 0 for sid in skill_ids}

        for step in combo.steps:
            for input_skill in step.inputs.values():
                if input_skill in skill_ids and input_skill != step.skill_id:
                    if step.skill_id not in adj[input_skill]:
                        adj[input_skill].add(step.skill_id)
                        in_degree[step.skill_id] += 1

        # Kahn's algorithm for topological sort
        queue = [sid for sid, deg in in_degree.items() if deg == 0]
        result: List[str] = []

        while queue:
            # Sort for deterministic ordering
            queue.sort()
            node = queue.pop(0)
            result.append(node)

            for neighbor in adj.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(skill_ids):
            raise ValueError(f"Circular dependency in {combo_id}")

        return result


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
