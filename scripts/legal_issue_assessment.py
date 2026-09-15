#!/usr/bin/env python3
"""Materialize the Operator-authored Issue / My assessment orientation layer.

This is a production-pipeline adapter for the reusable GlacierEQ legal primitive:
GlacierEQ/mega-skills/skills/legal-issue-assessment-matrix/SKILL.md

The adapter never invents the right-hand column. It validates and preserves supplied
Operator-authored assessments, plus stable pointers to existing source objects.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List


SCHEMA = "glaciereq.issue-my-assessment.v1"


def _list_of_strings(value: Any, field: str) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a string or list of strings")
    return [str(v).strip() for v in value if str(v).strip()]


def build_matrix(items: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    recovery_targets: List[str] = []

    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"item {index} must be an object")

        issue_id = str(item.get("issue_id") or item.get("proposition_id") or f"ISSUE-{index:04d}").strip()
        issue = str(item.get("issue") or item.get("statement") or "").strip()
        assessment = str(item.get("operator_assessment") or item.get("my_assessment") or "").strip()
        source = str(item.get("operator_assessment_source") or item.get("source_ref") or "").strip()

        if not issue:
            raise ValueError(f"{issue_id}: issue/statement is required")
        if not assessment:
            recovery_targets.append(issue_id)
            continue

        rows.append(
            {
                "issue_id": issue_id,
                "issue": issue,
                "my_assessment": assessment,
                "operator_assessment_source": source,
                "matter_pointers": _list_of_strings(item.get("matter_pointers"), "matter_pointers"),
                "fact_pointers": _list_of_strings(item.get("fact_pointers"), "fact_pointers"),
                "event_pointers": _list_of_strings(item.get("event_pointers"), "event_pointers"),
                "actor_pointers": _list_of_strings(item.get("actor_pointers"), "actor_pointers"),
                "evidence_pointers": _list_of_strings(item.get("evidence_pointers"), "evidence_pointers"),
                "authority_pointers": _list_of_strings(item.get("authority_pointers"), "authority_pointers"),
                "damage_pointers": _list_of_strings(item.get("damage_pointers"), "damage_pointers"),
                "remedy_pointers": _list_of_strings(item.get("remedy_pointers"), "remedy_pointers"),
            }
        )

    return {
        "schema": SCHEMA,
        "authority": "operator_authored_assessment",
        "rows": rows,
        "assessment_recovery_targets": recovery_targets,
        "analysis_separation": "assistant_or_agent_analysis_is_separate",
        "storage_model": "view_over_stable_objects_not_duplicate_fact_store",
        "shared_source": "GlacierEQ/mega-skills/skills/legal-issue-assessment-matrix/SKILL.md",
    }


def load_matrix_source(path: Path) -> Dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        items = raw.get("issues") or raw.get("propositions") or raw.get("rows")
        if items is None:
            raise ValueError("source object must contain issues, propositions, or rows")
    else:
        raise ValueError("source must be a JSON array or object")
    if not isinstance(items, list):
        raise ValueError("issue collection must be a list")
    return build_matrix(items)


def materialize_issue_assessment(source: Path, target_root: Path) -> Path:
    packet = load_matrix_source(source)
    output_dir = target_root / ".apex"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "issue_assessment_matrix.json"
    output.write_text(json.dumps(packet, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output
