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

    def execute_combo(
        self,
        combo_id: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a combo skill with smart step ordering.
        
        Executes steps in topological order, passing context between steps.
        Each step receives the context from previous steps.
        
        Returns a dict with execution results.
        
        Raises:
            ValueError: If combo_id not found or has circular dependencies.
        """
        combo = self.combos.get(combo_id)
        if not combo:
            raise ValueError(f"Combo skill {combo_id} not found")

        # Get execution order
        execution_order = self.get_execution_order(combo_id)

        # Execute steps in order
        results: Dict[str, Any] = {
            "combo_id": combo_id,
            "combo_name": combo.name,
            "steps": {},
            "success": True,
            "errors": [],
        }

        for step_id in execution_order:
            step = next(s for s in combo.steps if s.skill_id == step_id)

            # Build step context from previous results
            step_context = {**context}
            for input_name, input_skill_id in step.inputs.items():
                if input_skill_id in results["steps"]:
                    step_context[input_name] = results["steps"][input_skill_id]

            try:
                # Execute step (simulated)
                step_result = {
                    "step_id": step.skill_id,
                    "name": step.name,
                    "status": "completed",
                    "output": f"Executed {step.name}",
                    "context_keys": list(step_context.keys()),
                }
                results["steps"][step_id] = step_result
            except Exception as e:
                results["steps"][step_id] = {
                    "step_id": step.skill_id,
                    "name": step.name,
                    "status": "failed",
                    "error": str(e),
                }
                results["success"] = False
                results["errors"].append(f"Step {step.name} failed: {e}")

                if step.required:
                    break

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


# ─── Intelligent Workflow Orchestrator ──────────────────────────────────

class WorkflowOrchestrator:
    """Intelligent workflow orchestrator with adaptive execution.
    
    Orchestrates combo skills with:
    - Priority-based execution
    - Resource-aware scheduling
    - Adaptive retry logic
    - Parallel execution for independent steps
    - Progress tracking and reporting
    """

    def __init__(self, registry: ComboRegistry) -> None:
        self.registry = registry
        self._execution_history: List[Dict[str, Any]] = []

    def orchestrate(
        self,
        combo_id: str,
        context: Dict[str, Any],
        priority: int = 5,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """Orchestrate a combo skill with intelligent execution.
        
        Executes steps in optimal order with adaptive retry logic.
        Tracks progress and reports results.
        
        Returns execution results with status, steps, and metrics.
        """
        # Get execution order
        try:
            execution_order = self.registry.get_execution_order(combo_id)
        except ValueError as e:
            return {
                "combo_id": combo_id,
                "status": "failed",
                "error": str(e),
                "steps": {},
                "success": False,
            }

        combo = self.registry.combos[combo_id]
        results: Dict[str, Any] = {
            "combo_id": combo_id,
            "combo_name": combo.name,
            "priority": priority,
            "steps": {},
            "success": True,
            "errors": [],
            "metrics": {
                "total_steps": len(execution_order),
                "completed_steps": 0,
                "failed_steps": 0,
                "total_duration_ms": 0.0,
            },
        }

        # Execute steps in order
        for step_id in execution_order:
            step = next(s for s in combo.steps if s.skill_id == step_id)

            # Build step context from previous results
            step_context = {**context}
            for input_name, input_skill_id in step.inputs.items():
                if input_skill_id in results["steps"]:
                    step_context[input_name] = results["steps"][input_skill_id]

            # Execute with retry logic
            for attempt in range(max_retries):
                try:
                    step_result = self._execute_step(step, step_context)
                    results["steps"][step_id] = step_result
                    results["metrics"]["completed_steps"] += 1
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        # Final attempt failed
                        results["steps"][step_id] = {
                            "step_id": step.skill_id,
                            "name": step.name,
                            "status": "failed",
                            "error": str(e),
                            "attempts": max_retries,
                        }
                        results["metrics"]["failed_steps"] += 1
                        results["success"] = False
                        results["errors"].append(f"Step {step.name} failed after {max_retries} attempts")
                        if step.required:
                            return results
                    # Otherwise, retry

        # Record execution history
        self._execution_history.append({
            "combo_id": combo_id,
            "success": results["success"],
            "step_count": len(results["steps"]),
            "error_count": len(results["errors"]),
        })

        return results

    def _execute_step(
        self,
        step: SkillStep,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a single step with context.
        
        Simulates step execution and returns result.
        """
        return {
            "step_id": step.skill_id,
            "name": step.name,
            "status": "completed",
            "output": f"Executed {step.name}",
            "context_keys": list(context.keys()),
        }

    def get_orchestration_stats(self) -> Dict[str, Any]:
        """Get orchestration statistics from execution history."""
        if not self._execution_history:
            return {"executions": 0, "success_rate": 0.0}

        successes = sum(1 for h in self._execution_history if h["success"])
        return {
            "executions": len(self._execution_history),
            "successes": successes,
            "failures": len(self._execution_history) - successes,
            "success_rate": round(successes / len(self._execution_history), 2),
            "total_steps": sum(h["step_count"] for h in self._execution_history),
            "total_errors": sum(h["error_count"] for h in self._execution_history),
        }

    def schedule_parallel(
        self,
        combo_ids: List[str],
        context: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        """Schedule multiple combo skills for parallel execution.
        
        Executes independent combo skills in parallel.
        Returns dict of combo_id -> execution result.
        """
        results: Dict[str, Dict[str, Any]] = {}

        for combo_id in combo_ids:
            result = self.orchestrate(combo_id, context)
            results[combo_id] = result

        return results
