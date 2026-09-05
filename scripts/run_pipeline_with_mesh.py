#!/usr/bin/env python3
"""
run_pipeline_with_mesh.py — additive wrapper around the upstream
scripts/pipeline_runner.py. Does NOT modify the runner. Imports the
runner, drives it, and emits a Holographic Mesh receipt per phase via
apex_orchestration_overlay.

Holographic Mesh framing: many nodes, no single winner. The overlay
loads the canonical apex-orchestration v1.0.0 contract; the upstream
runner is one of many consumers.

Usage:
  python3 scripts/run_pipeline_with_mesh.py --target <workspace> [--skip Phase,Phase] [--strict-mesh]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Make the upstream runner importable
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# Import the canonical upstream pipeline_runner
import pipeline_runner  # noqa: E402

# Import our overlay (peer-skill contract loader)
import apex_orchestration_overlay as overlay  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Run pipeline with Holographic Mesh receipts"
    )
    ap.add_argument("--target", required=True, help="Target directory")
    ap.add_argument("--skip", default="", help="Comma-separated phase names to skip")
    ap.add_argument(
        "--strict-mesh",
        action="store_true",
        help="Hard-fail if apex-orchestration v1.0.0 is not loaded at L2",
    )
    ap.add_argument("--format", choices=["json", "markdown", "both"], default="both")
    args = ap.parse_args()

    contract = overlay.load_mesh_contract()
    if args.strict_mesh and (
        contract is None
        or not contract.all_maturity_nine_plus
        or contract.packet_count < 12
    ):
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "reason": "strict-mesh required but apex-orchestration v1.0.0 not loaded",
                    "contract_loaded": contract is not None,
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 3

    target = Path(args.target)
    if not target.is_dir():
        print(f"Error: {target} is not a directory", file=sys.stderr)
        return 1

    skip = [s.strip() for s in args.skip.split(",") if s.strip()]
    runner = pipeline_runner.PipelineRunner(str(target), skip_phases=skip)
    result = runner.run()

    # Now emit one mesh receipt per phase from the overlay.
    # We do not modify the runner; we synthesize the L2 proof from the
    # contract and per-phase result evidence.
    if (
        contract is not None
        and contract.all_maturity_nine_plus
        and contract.packet_count >= 12
    ):
        l2 = True
        chain = contract.chain_sha256()
        pc = contract.packet_count
    else:
        l2 = False
        chain = ""
        pc = 0

    mesh_receipts = []
    for phase in result.phases:
        r = overlay.PhaseReceipt(
            phase=phase.name,
            mesh_version=overlay.MESH_VERSION,
            packet_count=pc,
            chain_sha256=chain,
            l2_proof=l2,
            notes=phase.evidence or (phase.error or ""),
        )
        mesh_receipts.append(r.to_dict())

    output = {
        "task": result.task,
        "start_time": result.start_time,
        "end_time": result.end_time,
        "completed": f"{result.completed_phases}/{result.total_phases}",
        "gate_status": result.gate_status,
        "mesh_status": (
            "PRESENT"
            if (
                contract
                and contract.all_maturity_nine_plus
                and contract.packet_count >= 12
            )
            else "DEGRADED"
            if contract
            else "MISSING"
        ),
        "mesh_packet_count": pc,
        "mesh_chain_sha256": chain,
        "mesh_receipts": mesh_receipts,
        "phases": [
            {
                "name": p.name,
                "status": p.status.value,
                "duration_ms": round(p.duration_ms, 1),
                "evidence": p.evidence,
                "error": p.error,
                "artifacts": p.artifacts,
            }
            for p in result.phases
        ],
    }

    if args.format in ("json", "both"):
        print(json.dumps(output, indent=2))
    if args.format in ("markdown", "both"):
        lines = [
            "# Pipeline Result (Holographic Mesh Overlay)",
            "",
            f"- Task: {result.task}",
            f"- Phases: {result.completed_phases}/{result.total_phases}",
            f"- Gate: {result.gate_status}",
            f"- Mesh: {output['mesh_status']} ({pc} packets, chain={chain[:12]}\u2026)",
            "",
            "## Mesh Receipts (L2)",
        ]
        for r in mesh_receipts:
            lines.append(
                f"- {r['phase']}: chain={r['chain_sha256'][:12]}\u2026 l2={r['l2_proof']}"
            )
        print("\n" + "\n".join(lines))

    return 0 if result.all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
