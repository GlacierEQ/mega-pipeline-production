#!/usr/bin/env python3
"""
apex-orchestration overlay for mega-pipeline-production.

Holographic Mesh integration: the runner is one node in a mesh of many. It does
not duplicate the lower-layer methods defined in apex-orchestration v1.0.0
(skills/apex-orchestration/SKILL.md + 12 logic packets). Instead, it loads the
canonical contract and emits L2 mesh receipts at every phase transition.

Add to scripts/. Imported by pipeline_runner.py via a try/except (no import
cycle, no breaking change to upstream).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


MESH_VERSION = "1.0.0"

_CANDIDATE_ROOTS = [
    (
        Path(os.environ["APEX_ORCH_ROOT"]) / "skills/apex-orchestration"
        if os.environ.get("APEX_ORCH_ROOT")
        else None
    ),
    Path.home()
    / "APEX_SYSTEM/DOMAINS/SWARM_INTELLIGENCE/SWARM_TECH/mega-skills/skills/apex-orchestration",
    Path.home() / ".kilo/skills/apex-orchestration",
    Path("/opt/apex-orchestration"),
]
_CANDIDATE_ROOTS = [p for p in _CANDIDATE_ROOTS if p is not None]


def locate_apex_orchestration() -> Optional[Path]:
    """Return the canonical apex-orchestration skill root, or None.

    If APEX_ORCH_ROOT is set, ONLY that path is searched (used by tests
    to point the overlay at a degraded or missing location for the
    strict-mesh BLOCK case). Otherwise, the standard candidate list is
    walked in order and the first hit wins.
    """
    override = os.environ.get("APEX_ORCH_ROOT")
    if override:
        p = Path(override) / "skills/apex-orchestration"
        if (p / "SKILL.md").exists() and (p / "packets").is_dir():
            return p
        # Override is set but invalid — return None (strict-mesh will BLOCK).
        return None
    for p in _CANDIDATE_ROOTS:
        if (p / "SKILL.md").exists() and (p / "packets").is_dir():
            return p
    return None


@dataclass
class PacketMeta:
    id: str
    name: str
    title: str
    maturity: int
    version: str
    path: Path
    sha256: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "title": self.title,
            "maturity": self.maturity,
            "version": self.version,
            "sha256": self.sha256,
            "path": str(self.path),
        }


@dataclass
class MeshContract:
    skill_root: Path
    packets: List[PacketMeta] = field(default_factory=list)
    lanes: List[Dict[str, str]] = field(default_factory=list)
    routes: List[Dict[str, Any]] = field(default_factory=list)
    failure_codes: List[Dict[str, str]] = field(default_factory=list)
    receipt_schema: Dict[str, Any] = field(default_factory=dict)
    delivery_schema: Dict[str, Any] = field(default_factory=dict)

    @property
    def packet_count(self) -> int:
        return len(self.packets)

    @property
    def all_maturity_nine_plus(self) -> bool:
        return all(p.maturity >= 9 for p in self.packets)

    def chain_sha256(self) -> str:
        h = hashlib.sha256()
        for p in sorted(self.packets, key=lambda x: x.id):
            if p.path.exists():
                h.update(p.path.read_bytes())
        return h.hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_root": str(self.skill_root),
            "mesh_version": MESH_VERSION,
            "packet_count": self.packet_count,
            "all_maturity_nine_plus": self.all_maturity_nine_plus,
            "chain_sha256": self.chain_sha256(),
            "packets": [p.to_dict() for p in self.packets],
            "lane_count": len(self.lanes),
            "route_count": len(self.routes),
            "failure_code_count": len(self.failure_codes),
        }


_LANE_TABLE = [
    (
        "REASON",
        "nvidia/nemotron-3-ultra-550b-a55b:free",
        "plan_required OR invariants > 3 OR cross_domain",
    ),
    ("CODE", "poolside/laguna-s-2.1:free", "code_edit OR code_create"),
    (
        "CODE-FAST",
        "poolside/laguna-xs-2.1:free",
        "subagent == true AND scope < 200_lines",
    ),
    ("VERIFY", "z-ai/glm-5.2:free", "verify_required OR audit"),
    ("REVIEW", "cohere/north-mini-code:free", "refactor OR simplify"),
    ("LONG-CTX", "thinkingmachines/inkling:free", "input_tokens > 500_000"),
    (
        "LONG-CTX-ALT",
        "minimax/minimax-m3:free",
        "input_tokens > 500_000 AND inkling_unavailable",
    ),
    (
        "THINK-DEEP",
        "minimax/minimax-m2.7:free",
        "mission.horizon == long AND requires_evolution",
    ),
    (
        "NANO-PERCEPTION",
        "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        "input_modality IN {image, video, audio}",
    ),
    (
        "DOMAIN-MED",
        "inclusionai/ling-3.0-flash-sante:free",
        "domain == medical OR clinical",
    ),
    (
        "DOMAIN-FIN",
        "inclusionai/ling-3.0-flash-fin:free",
        "domain == finance OR quantitative",
    ),
    (
        "ROUTER-FREE",
        "openrouter/free",
        "smoke_test OR cost == 0 AND quality < critical",
    ),
]

_ROUTE_TABLE = [
    ("R-MEDICAL", "DOMAIN-MED", "subtask.domain IN {medical, clinical}", True),
    ("R-FINANCE", "DOMAIN-FIN", "subtask.domain IN {finance, quantitative}", True),
    (
        "R-MULTIMODAL",
        "NANO-PERCEPTION",
        "subtask.input_modality IN {image, video, audio}",
        True,
    ),
    ("R-LONGCTX", "LONG-CTX", "subtask.input_tokens > 500_000", True),
    (
        "R-PLAN",
        "REASON",
        "subtask.kind == plan OR invariants > 3 OR cross_domain",
        True,
    ),
    ("R-CODE-EDIT", "CODE", "subtask.kind IN {code_edit, code_create}", False),
    (
        "R-CODE-FAST",
        "CODE-FAST",
        "subtask.subagent == true AND estimated_lines < 200",
        False,
    ),
    ("R-DEFAULT", "ROUTER-FREE", "always (with VERIFY audit)", False),
]

_FAILURE_TABLE = [
    ("F-INT-01", "scope_ambiguous", "INTAKE", "operator", "ask one question, BLOCK"),
    ("F-INT-02", "budget_exceeded", "INTAKE", "operator", "BLOCK with cost breakdown"),
    ("F-DEC-01", "dag_cycle", "DECOMPOSE", "operator", "refuse DAG, re-decompose"),
    ("F-DEC-02", "lane_unavailable", "DECOMPOSE", "operator", "swap to fallback"),
    (
        "F-DIS-01",
        "dispatch_timeout",
        "DISPATCH",
        "orchestrator",
        "re-dispatch once, then BLOCK",
    ),
    ("F-DIS-02", "quota_exhausted", "DISPATCH", "orchestrator", "BLOCK mission"),
    ("F-VER-01", "l2_proof_missing", "VERIFY", "operator", "re-dispatch"),
    (
        "F-VER-02",
        "three_sig_missing",
        "VERIFY",
        "operator",
        "re-dispatch missing signature",
    ),
    ("F-FUSE-01", "draft_input", "FUSE", "operator", "drop drafts, BLOCK if empty"),
    ("F-FUSE-02", "conflict_unresolved", "FUSE", "operator", "BLOCK with both options"),
    (
        "F-DEL-01",
        "memory_write_failed",
        "DELIVERY",
        "operator",
        "BLOCK, retry once, then REFUSE",
    ),
    ("F-DEL-02", "chain_hash_drift", "DELIVERY", "operator", "REFUSE"),
]


def _parse_packet(p: Path) -> Optional[PacketMeta]:
    if not p.exists() or not p.name.endswith(".md"):
        return None
    txt = p.read_text(encoding="utf-8")
    m = re.match(r"^(\d+)-([a-z-]+)\.md$", p.name)
    if not m:
        return None
    pid, name = m.group(1), m.group(2)
    title = ""
    for line in txt.splitlines():
        if line.startswith("# Packet"):
            title = line.lstrip("# ").strip()
            break
    maturity = 0
    for line in txt.splitlines():
        if line.startswith("**Maturity:**"):
            mm = re.search(r"(\d+)", line)
            if mm:
                maturity = int(mm.group(1))
            break
    version = ""
    for line in txt.splitlines():
        if line.startswith("Current version:"):
            version = line.split(":", 1)[1].strip()
            break
    return PacketMeta(
        id=pid,
        name=name,
        title=title,
        maturity=maturity,
        version=version,
        path=p,
        sha256=hashlib.sha256(txt.encode()).hexdigest(),
    )


def load_mesh_contract() -> Optional[MeshContract]:
    root = locate_apex_orchestration()
    if root is None:
        return None
    contract = MeshContract(skill_root=root)
    packets_dir = root / "packets"
    if packets_dir.is_dir():
        for f in sorted(packets_dir.glob("*.md")):
            meta = _parse_packet(f)
            if meta is not None:
                contract.packets.append(meta)
    for lane, model, trigger in _LANE_TABLE:
        contract.lanes.append({"lane": lane, "model": model, "trigger": trigger})
    for rule, lane, pred, hard in _ROUTE_TABLE:
        contract.routes.append(
            {"rule": rule, "lane": lane, "predicate": pred, "hard_gate": hard}
        )
    for code, name, stage, owner, res in _FAILURE_TABLE:
        contract.failure_codes.append(
            {
                "code": code,
                "name": name,
                "stage": stage,
                "owner": owner,
                "resolution": res,
            }
        )
    schemas_dir = root / "schemas"
    if schemas_dir.is_dir():
        for name, attr in [
            ("receipt.schema.json", "receipt_schema"),
            ("delivery.schema.json", "delivery_schema"),
        ]:
            p = schemas_dir / name
            if p.exists():
                try:
                    setattr(contract, attr, json.loads(p.read_text()))
                except json.JSONDecodeError:
                    pass
    return contract


@dataclass
class PhaseReceipt:
    phase: str
    mesh_version: str
    packet_count: int
    chain_sha256: str
    l2_proof: bool
    ts: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ"))
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase,
            "mesh_version": self.mesh_version,
            "packet_count": self.packet_count,
            "chain_sha256": self.chain_sha256,
            "l2_proof": self.l2_proof,
            "ts": self.ts,
            "notes": self.notes,
        }


def emit_phase_receipt(
    phase: str, contract: MeshContract, notes: str = ""
) -> PhaseReceipt:
    l2 = (
        contract is not None
        and contract.all_maturity_nine_plus
        and contract.packet_count >= 12
    )
    return PhaseReceipt(
        phase=phase,
        mesh_version=MESH_VERSION,
        packet_count=contract.packet_count if contract else 0,
        chain_sha256=contract.chain_sha256() if contract else "",
        l2_proof=l2,
        notes=notes,
    )


def main() -> int:
    contract = load_mesh_contract()
    if contract is None:
        print(
            json.dumps(
                {
                    "mesh_version": MESH_VERSION,
                    "status": "apex_orchestration_not_found",
                    "searched": [str(p) for p in _CANDIDATE_ROOTS],
                },
                indent=2,
            )
        )
        return 2
    print(json.dumps(contract.to_dict(), indent=2))
    return 0 if contract.all_maturity_nine_plus and contract.packet_count >= 12 else 1


if __name__ == "__main__":
    sys.exit(main())
