#!/usr/bin/env python3
"""
APEX HIGH-SIGNAL COMPANIES — Production-Grade Verification Suite
End-to-end verification of all 7 domain modules.
"""

import subprocess
import sys
import time
from pathlib import Path

MODULES_DIR = Path(__file__).parent

TESTS = [
    ("apex_nasa_telemetry_gate.py", ["verify", "-n", "100"]),
    ("apex_constellation_mesh.py", ["simulate", "--sats", "50", "--stations", "10", "--handovers", "200"]),
    ("apex_gpu_topology_engine.py", ["place", "--gpus", "8", "--jobs", "10"]),
    ("apex_f35_verification_pipeline.py", ["build", "-n", "10", "--retries", "3"]),
    ("apex_ew_signal_fabric.py", ["scan", "-n", "200"]),
    ("apex_cmmc_compliance_engine.py", ["assess", "--level", "2"]),
    ("apex_swarm_forge.py", ["engage", "--drones", "50", "--count", "10"]),
]


def run_test(module: str, args: list) -> dict:
    cmd = [sys.executable, str(MODULES_DIR / module)] + args
    t0 = time.perf_counter_ns()
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    elapsed_ms = (time.perf_counter_ns() - t0) / 1_000_000
    return {
        "module": module,
        "passed": result.returncode == 0,
        "exit_code": result.returncode,
        "elapsed_ms": round(elapsed_ms, 1),
        "output_lines": len(result.stdout.strip().split("\n")) if result.stdout else 0,
        "error": result.stderr.strip().split("\n")[-3:] if result.returncode != 0 and result.stderr else [],
    }


def main():
    print("=" * 72)
    print("  APEX HIGH-SIGNAL COMPANIES — Production-Grade Verification Suite")
    print("=" * 72)
    print()

    results = []
    total_ms = 0
    for module, args in TESTS:
        r = run_test(module, args)
        results.append(r)
        total_ms += r["elapsed_ms"]
        icon = "PASS" if r["passed"] else "FAIL"
        print(f"  [{icon}] {module}: {r['elapsed_ms']}ms ({r['output_lines']} lines output)")
        if not r["passed"]:
            for line in r["error"]:
                print(f"         {line}")

    passed = sum(1 for r in results if r["passed"])
    total = len(results)

    print()
    print(f"  Results: {passed}/{total} modules verified")
    print(f"  Total time: {total_ms:.1f}ms")
    print()

    if passed == total:
        print("  ALL MODULES PRODUCTION-GRADE VERIFIED")
    else:
        print(f"  {total - passed} MODULE(S) FAILED VERIFICATION")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
