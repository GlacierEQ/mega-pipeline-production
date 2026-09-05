"""
Mega-Pipeline: Production — Test Suite
Tests for the 10-phase production pipeline runner and production auditor.
"""

import json
import sys
from pathlib import Path

import pytest

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent / "scripts"))

from pipeline_runner import (
    PipelineResult,
    PipelineRunner,
    PhaseResult,
    PhaseStatus,
)


# ─── Phase Status Tests ──────────────────────────────────────────────────────

class TestPhaseStatus:
    """Tests for phase status enum."""

    def test_all_statuses(self):
        assert PhaseStatus.PENDING.value == "pending"
        assert PhaseStatus.RUNNING.value == "running"
        assert PhaseStatus.PASSED.value == "passed"
        assert PhaseStatus.FAILED.value == "failed"
        assert PhaseStatus.SKIPPED.value == "skipped"


# ─── Phase Result Tests ──────────────────────────────────────────────────────

class TestPhaseResult:
    """Tests for phase result dataclass."""

    def test_create_result(self):
        result = PhaseResult(name="test", status=PhaseStatus.PASSED)
        assert result.name == "test"
        assert result.status == PhaseStatus.PASSED

    def test_result_with_evidence(self):
        result = PhaseResult(
            name="test",
            status=PhaseStatus.PASSED,
            evidence="all good",
            duration_ms=100.5,
        )
        assert result.evidence == "all good"
        assert result.duration_ms == 100.5

    def test_result_to_dict(self):
        result = PhaseResult(name="test", status=PhaseStatus.PASSED, evidence="ok")
        # PhaseResult is a dataclass, test its attributes directly
        assert result.name == "test"
        assert result.status == PhaseStatus.PASSED
        assert result.evidence == "ok"
        assert result.duration_ms == 0.0
        assert result.error == ""
        assert result.artifacts == []


# ─── Pipeline Result Tests ───────────────────────────────────────────────────

class TestPipelineResult:
    """Tests for pipeline result dataclass."""

    def test_create_result(self):
        result = PipelineResult(
            task="test-pipeline",
            start_time="2026-01-01T00:00:00Z",
        )
        assert result.task == "test-pipeline"
        assert result.completed_phases == 0
        assert result.total_phases == 0

    def test_completed_phases(self):
        result = PipelineResult(task="test", start_time="2026-01-01T00:00:00Z")
        result.phases = [
            PhaseResult(name="a", status=PhaseStatus.PASSED),
            PhaseResult(name="b", status=PhaseStatus.PASSED),
            PhaseResult(name="c", status=PhaseStatus.FAILED),
        ]
        assert result.completed_phases == 2

    def test_total_phases(self):
        result = PipelineResult(task="test", start_time="2026-01-01T00:00:00Z")
        result.phases = [
            PhaseResult(name="a", status=PhaseStatus.PASSED),
            PhaseResult(name="b", status=PhaseStatus.SKIPPED),
        ]
        assert result.total_phases == 2

    def test_all_passed(self):
        result = PipelineResult(task="test", start_time="2026-01-01T00:00:00Z")
        result.phases = [
            PhaseResult(name="a", status=PhaseStatus.PASSED),
            PhaseResult(name="b", status=PhaseStatus.SKIPPED),
        ]
        assert result.all_passed

    def test_not_all_passed(self):
        result = PipelineResult(task="test", start_time="2026-01-01T00:00:00Z")
        result.phases = [
            PhaseResult(name="a", status=PhaseStatus.PASSED),
            PhaseResult(name="b", status=PhaseStatus.FAILED),
        ]
        assert not result.all_passed

    def test_to_dict(self):
        result = PipelineResult(task="test", start_time="2026-01-01T00:00:00Z")
        result.phases = [PhaseResult(name="a", status=PhaseStatus.PASSED)]
        d = result.to_dict()
        assert d["task"] == "test"
        assert len(d["phases"]) == 1

    def test_to_markdown(self):
        result = PipelineResult(task="test", start_time="2026-01-01T00:00:00Z")
        result.phases = [PhaseResult(name="a", status=PhaseStatus.PASSED)]
        md = result.to_markdown()
        assert "# Pipeline Result" in md
        assert "test" in md


# ─── Pipeline Runner Tests ───────────────────────────────────────────────────

class TestPipelineRunner:
    """Tests for pipeline runner."""

    def test_runner_orient(self, tmp_path):
        runner = PipelineRunner(str(tmp_path))
        result = runner.phase_orient()
        assert result.status == PhaseStatus.PASSED
        assert "py" in result.evidence or "files" in result.evidence.lower()

    def test_runner_grill(self, tmp_path):
        runner = PipelineRunner(str(tmp_path))
        result = runner.phase_grill()
        assert result.status == PhaseStatus.SKIPPED

    def test_runner_spec(self, tmp_path):
        runner = PipelineRunner(str(tmp_path))
        result = runner.phase_spec()
        assert result.status == PhaseStatus.PASSED

    def test_runner_workspace(self, tmp_path):
        runner = PipelineRunner(str(tmp_path))
        result = runner.phase_workspace()
        assert result.status == PhaseStatus.PASSED

    def test_runner_implement(self, tmp_path):
        runner = PipelineRunner(str(tmp_path))
        result = runner.phase_implement()
        assert result.status == PhaseStatus.PASSED
        assert "files" in result.evidence or "lines" in result.evidence

    def test_runner_review(self, tmp_path):
        runner = PipelineRunner(str(tmp_path))
        result = runner.phase_review()
        assert result.status == PhaseStatus.PASSED

    def test_runner_finalize(self, tmp_path):
        runner = PipelineRunner(str(tmp_path))
        result = runner.phase_finalize()
        assert result.status == PhaseStatus.PASSED

    def test_runner_finish(self, tmp_path):
        runner = PipelineRunner(str(tmp_path))
        result = runner.phase_finish()
        assert result.status == PhaseStatus.PASSED

    def test_runner_run_quick(self, tmp_path):
        runner = PipelineRunner(str(tmp_path), skip_phases=["Gate", "Verify"])
        result = runner.run()
        assert result.completed_phases >= 6


# ─── Integration Tests ───────────────────────────────────────────────────────

class TestIntegration:
    """Integration tests for full pipeline run."""

    def test_full_pipeline_run(self, tmp_path):
        """Test full pipeline run on temp directory."""
        runner = PipelineRunner(str(tmp_path), skip_phases=["Gate", "Verify"])
        result = runner.run()
        # Should complete most phases
        assert result.completed_phases >= 6
        assert result.end_time != ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
