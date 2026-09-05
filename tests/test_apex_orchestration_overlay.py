"""
tests/test_apex_orchestration_overlay.py — overlay tests for the
Holographic Mesh integration. Does not touch upstream's test files.
"""

import inspect
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import apex_orchestration_overlay as overlay  # noqa: E402
import pipeline_runner  # noqa: E402


class TestOverlayContract(unittest.TestCase):
    def test_overlay_loads_apex_orchestration(self):
        c = overlay.load_mesh_contract()
        self.assertIsNotNone(c)
        # v1.0.0 had 12 packets; v1.1.0+ has 16. Accept either.
        self.assertGreaterEqual(c.packet_count, 12)
        self.assertTrue(c.all_maturity_nine_plus)

    def test_overlay_chain_deterministic(self):
        c = overlay.load_mesh_contract()
        self.assertEqual(c.chain_sha256(), c.chain_sha256())
        self.assertEqual(len(c.chain_sha256()), 64)

    def test_overlay_lane_route_failure_counts(self):
        c = overlay.load_mesh_contract()
        self.assertEqual(len(c.lanes), 12)
        self.assertEqual(len(c.routes), 8)
        self.assertEqual(len(c.failure_codes), 12)


class TestOverlayPipeline(unittest.TestCase):
    def _make_target(self) -> Path:
        d = Path(tempfile.mkdtemp(prefix="mpp_mesh_"))
        (d / "pyproject.toml").write_text("[project]\nname='t'\n")
        (d / "src").mkdir()
        (d / "src" / "main.py").write_text("x = 1\n")
        return d

    def test_wrapper_emits_mesh_receipts(self):
        d = self._make_target()
        try:
            r = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "run_pipeline_with_mesh.py"),
                    "--target",
                    str(d),
                    "--skip",
                    "Gate,Verify",
                    "--format",
                    "json",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(r.returncode, 0, msg=r.stderr)
            out = json.loads(r.stdout)
            self.assertEqual(out["mesh_status"], "PRESENT")
            # v1.0.0 had 12 packets; v1.1.0+ has 16. Accept either.
            self.assertGreaterEqual(out["mesh_packet_count"], 12)
            self.assertEqual(len(out["mesh_receipts"]), 10)
            for receipt in out["mesh_receipts"]:
                self.assertTrue(
                    receipt["l2_proof"], f"phase {receipt['phase']} missing L2 proof"
                )
                self.assertEqual(len(receipt["chain_sha256"]), 64)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_wrapper_strict_mesh_blocks_on_degraded_contract(self):
        """Set APEX_ORCH_ROOT to a path with SKILL.md but no packets/ — a
        degraded contract. strict-mesh must exit 3 (block)."""
        d = self._make_target()
        broken = Path(tempfile.mkdtemp(prefix="apex_broken_"))
        try:
            (broken / "SKILL.md").write_text("---\nname: broken\n---\n")
            r = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "run_pipeline_with_mesh.py"),
                    "--target",
                    str(d),
                    "--strict-mesh",
                    "--skip",
                    "Gate,Verify,Grill,Spec,Review,Finalize,Finish,Workspace,Implement,Orient",
                ],
                env={**os.environ, "APEX_ORCH_ROOT": str(broken)},
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(r.returncode, 3, msg=r.stderr)
        finally:
            shutil.rmtree(broken, ignore_errors=True)
            shutil.rmtree(d, ignore_errors=True)

    def test_wrapper_does_not_modify_upstream_runner(self):
        """The overlay is purely additive. The upstream PipelineRunner class
        signature is untouched."""
        sig = inspect.signature(pipeline_runner.PipelineRunner.__init__)
        self.assertIn("target", sig.parameters)
        self.assertIn("skip_phases", sig.parameters)
        self.assertNotIn("strict_mesh", sig.parameters)


if __name__ == "__main__":
    unittest.main()
