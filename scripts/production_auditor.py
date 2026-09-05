#!/usr/bin/env python3
"""
Production Readiness Auditor — Scans codebases for 7 production dimensions.

Usage:
    python3 production_auditor.py --target <dir> --dimension all
    python3 production_auditor.py --target <dir> --dimension 1,3,5
    python3 production_auditor.py --target <dir> --format sarif
    python3 production_auditor.py --target <dir> --ci
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Sequence


# ─── Constants ───────────────────────────────────────────────────────────────

VERSION = "2.0.0"

DIMENSION_NAMES = {
    1: "Tests",
    2: "Config",
    3: "Telemetry",
    4: "Persistence",
    5: "API Surface",
    6: "Error Recovery",
    7: "Integration",
}

SEVERITY_ORDER = {"INFO": 0, "WARNING": 1, "CRITICAL": 2}


class GateStatus(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"


@dataclass(frozen=True)
class ExitCode:
    """CI-friendly exit codes."""
    SUCCESS = 0
    GATE_FAILED = 1
    AUDIT_ERROR = 2


# ─── Data Models ─────────────────────────────────────────────────────────────

@dataclass
class Finding:
    dimension: str
    dimension_num: int
    status: str  # PASS, FAIL, WARN
    message: str
    evidence: str
    severity: str = "INFO"  # INFO, WARNING, CRITICAL
    remediation: str = ""
    file_path: Optional[str] = None
    line_number: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("file_path", None)
        d.pop("line_number", None)
        return d


@dataclass
class AuditReport:
    target: str
    timestamp: str
    version: str
    findings: List[Finding] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0

    @property
    def gate_status(self) -> GateStatus:
        failed = [f for f in self.findings if f.status == "FAIL"]
        if not failed:
            return GateStatus.PASS
        criticals = [f for f in failed if f.severity == "CRITICAL"]
        if criticals:
            return GateStatus.FAIL
        return GateStatus.FAIL

    @property
    def passed_count(self) -> int:
        return sum(1 for f in self.findings if f.status == "PASS")

    @property
    def failed_count(self) -> int:
        return sum(1 for f in self.findings if f.status == "FAIL")

    @property
    def warned_count(self) -> int:
        return sum(1 for f in self.findings if f.status == "WARN")

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "CRITICAL")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target": self.target,
            "timestamp": self.timestamp,
            "version": self.version,
            "duration_ms": round(self.duration_ms, 1),
            "gate_status": self.gate_status.value,
            "summary": {
                "total": len(self.findings),
                "passed": self.passed_count,
                "failed": self.failed_count,
                "warned": self.warned_count,
                "critical": self.critical_count,
            },
            "findings": [f.to_dict() for f in self.findings],
        }

    def to_sarif(self) -> Dict[str, Any]:
        """Convert to SARIF format for GitHub Security tab integration."""
        runs = []
        results = []
        for f in self.findings:
            if f.status == "PASS":
                continue
            level = "error" if f.severity == "CRITICAL" else "warning"
            result = {
                "ruleId": f"PRD-{f.dimension_num:02d}",
                "message": {"text": f"{f.dimension}: {f.message}"},
                "level": level,
                "locations": [{
                    "physicalLocation": {
                        "artifactLocation": {"uri": f.file_path or "unknown"},
                        "region": {"startLine": f.line_number or 1},
                    }
                }],
            }
            if f.remediation:
                result["fixes"] = [{"description": {"text": f.remediation}}]
            results.append(result)

        return {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [{
                "tool": {
                    "driver": {
                        "name": "production-readiness-auditor",
                        "version": VERSION,
                        "rules": [
                            {
                                "id": f"PRD-{i:02d}",
                                "shortDescription": {"text": name},
                                "helpUri": f"https://github.com/GlacierEQ/production-readiness-gate#dim{i}",
                            }
                            for i, name in DIMENSION_NAMES.items()
                        ],
                    }
                },
                "results": results,
            }],
        }

    def to_github_actions(self) -> str:
        """Format as GitHub Actions annotations."""
        lines = []
        for f in self.findings:
            if f.status == "PASS":
                continue
            severity = "::error" if f.severity == "CRITICAL" else "::warning"
            lines.append(
                f"{severity} file={f.file_path or 'unknown'},"
                f"line={f.line_number or 1},"
                f"title=[PRD-{f.dimension_num:02d}] {f.dimension}: {f.status},"
                f"{f.message}"
            )
        return "\n".join(lines)


# ─── Auditor ─────────────────────────────────────────────────────────────────

class ProductionAuditor:
    """Scans Python codebases for production readiness across 7 dimensions."""

    def __init__(self, target: str, severity_threshold: str = "WARNING") -> None:
        self.target = Path(target)
        self.findings: List[Finding] = []
        self.severity_threshold = severity_threshold
        self._start_time = 0.0

    def _scan_files(self, pattern: str = "**/*.py") -> List[Path]:
        """Scan for files, excluding common non-source directories."""
        excludes = {"__pycache__", ".git", ".venv", "node_modules", ".worktrees"}
        results = []
        for f in self.target.glob(pattern):
            if not any(part in excludes for part in f.parts):
                results.append(f)
        return results

    def audit_dimension_1_tests(self) -> None:
        """Dimension 1: Tests exist and are runnable."""
        test_files = [f for f in self._scan_files("**/test_*.py")
                      if not any(part in ("__pycache__",) for part in f.parts)]

        if not test_files:
            self.findings.append(Finding(
                dimension="Tests", dimension_num=1, status="FAIL",
                message="No test files found (expected test_*.py)",
                evidence=f"Searched: {self.target}",
                severity="CRITICAL",
                remediation="Create pytest suite with test_*.py files covering core logic",
            ))
            return

        has_asserts = False
        has_fixtures = False
        has_parametrize = False
        total_tests = 0
        test_classes = 0

        for tf in test_files:
            try:
                content = tf.read_text()
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Assert):
                        has_asserts = True
                    if isinstance(node, ast.Name) and "fixture" in node.id.lower():
                        has_fixtures = True
                    if isinstance(node, ast.Name) and "parametrize" in node.id.lower():
                        has_parametrize = True
                    if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                        test_classes += 1
                    if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                        total_tests += 1
            except (SyntaxError, UnicodeDecodeError):
                pass

        evidence_parts = [f"{len(test_files)} test files"]
        if total_tests >= 10:
            evidence_parts.append(f"{total_tests} tests")
        if test_classes >= 3:
            evidence_parts.append(f"{test_classes} test classes")
        if has_fixtures:
            evidence_parts.append("fixtures")
        if has_parametrize:
            evidence_parts.append("parametrize")

        status = "PASS" if total_tests >= 3 and has_asserts else "FAIL"
        self.findings.append(Finding(
            dimension="Tests", dimension_num=1, status=status,
            message=f"Found {total_tests} test functions, assertions={has_asserts}",
            evidence=", ".join(evidence_parts),
            severity="CRITICAL" if status == "FAIL" else "INFO",
            remediation="Add more test functions with assert statements" if status == "FAIL" else "",
        ))

    def audit_dimension_2_config(self) -> None:
        """Dimension 2: No hardcoded constants — config is externalized."""
        py_files = self._scan_files()
        hardcoded_count = 0
        magic_numbers: List[str] = []
        config_files = (
            list(self.target.glob("**/*.toml"))
            + list(self.target.glob("**/*.yaml"))
            + list(self.target.glob("**/*.yml"))
            + list(self.target.glob("**/config*.py"))
            + list(self.target.glob("**/settings*.py"))
        )

        # Constants to exclude from magic number detection
        safe_values = frozenset({0, 1, -1, 0.0, 1.0, 2, 10, 100, 1000, 0.5})

        for pf in py_files:
            try:
                content = pf.read_text()
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Assign):
                        for target in node.targets:
                            if isinstance(target, ast.Name):
                                if isinstance(node.value, ast.Constant) and \
                                   isinstance(node.value.value, (int, float)) and \
                                   node.value.value not in safe_values:
                                    hardcoded_count += 1
                                    if len(magic_numbers) < 5:
                                        magic_numbers.append(
                                            f"{target.id}={node.value.value} (line {node.lineno})"
                                        )
            except (SyntaxError, UnicodeDecodeError):
                pass

        has_config = len(config_files) > 0
        status = "PASS" if has_config or hardcoded_count < 3 else "FAIL"
        self.findings.append(Finding(
            dimension="Config", dimension_num=2, status=status,
            message=f"Hardcoded constants: {hardcoded_count}, config files: {len(config_files)}",
            evidence=f"Config: {[f.name for f in config_files]}, Magic: {magic_numbers}",
            severity="WARNING" if hardcoded_count >= 3 else "INFO",
            remediation="Externalize constants to TOML/YAML config or dataclass defaults" if status == "FAIL" else "",
        ))

    def audit_dimension_3_telemetry(self) -> None:
        """Dimension 3: Structured logging and metrics exist."""
        py_files = self._scan_files()
        has_logging = False
        has_metrics = False
        has_structured_logging = False
        log_imports: List[str] = []

        for pf in py_files:
            try:
                content = pf.read_text()
                if "import logging" in content or "from logging" in content:
                    has_logging = True
                    log_imports.append(pf.name)
                if any(x in content for x in ["metrics", "counter", "histogram", "gauge"]):
                    has_metrics = True
                if "extra=" in content or "getLogger(__name__)" in content:
                    has_structured_logging = True
            except (SyntaxError, UnicodeDecodeError):
                pass

        status = "PASS" if has_logging else "FAIL"
        evidence = f"Logging in: {len(log_imports)} modules"
        if has_metrics:
            evidence += ", metrics: yes"
        if has_structured_logging:
            evidence += ", structured: yes"

        self.findings.append(Finding(
            dimension="Telemetry", dimension_num=3, status=status,
            message=f"Logging: {has_logging}, Metrics: {has_metrics}, Structured: {has_structured_logging}",
            evidence=evidence,
            severity="CRITICAL" if status == "FAIL" else "INFO",
            remediation="Add 'import logging' and logger = logging.getLogger(__name__) to modules" if status == "FAIL" else "",
        ))

    def audit_dimension_4_persistence(self) -> None:
        """Dimension 4: State can survive restarts."""
        py_files = self._scan_files()
        has_persistence = False
        has_snapshots = False
        persistence_files: List[str] = []

        for pf in py_files:
            try:
                content = pf.read_text()
                if any(x in content for x in ["json.dump", "jsonl", "open(", "shelve", "sqlite"]):
                    has_persistence = True
                    persistence_files.append(pf.name)
                if any(x in content for x in ["to_json", "to_dict", "save_state", "snapshot"]):
                    has_persistence = True
                if "jsonl" in content or "snapshot" in content:
                    has_snapshots = True
            except (SyntaxError, UnicodeDecodeError):
                pass

        status = "PASS" if has_persistence else "FAIL"
        self.findings.append(Finding(
            dimension="Persistence", dimension_num=4, status=status,
            message=f"Persistence: {has_persistence}, Snapshots: {has_snapshots}",
            evidence=f"Files with persistence: {persistence_files[:5]}",
            severity="WARNING" if status == "FAIL" else "INFO",
            remediation="Add JSONL state snapshots or save/load methods to core classes" if status == "FAIL" else "",
        ))

    def audit_dimension_5_api_surface(self) -> None:
        """Dimension 5: Public API is documented and usable."""
        py_files = self._scan_files()
        public_methods = 0
        documented_methods = 0
        has_init = False
        has_type_hints = False
        has_dataclasses = False

        for pf in py_files:
            try:
                content = pf.read_text()
                tree = ast.parse(content)
                if pf.name == "__init__.py":
                    has_init = True
                if "@dataclass" in content:
                    has_dataclasses = True
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        for item in node.body:
                            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                if not item.name.startswith("_"):
                                    public_methods += 1
                                    if ast.get_docstring(item):
                                        documented_methods += 1
                                    if item.returns:
                                        has_type_hints = True
            except (SyntaxError, UnicodeDecodeError):
                pass

        doc_ratio = documented_methods / max(public_methods, 1)
        status = "PASS" if public_methods > 0 and doc_ratio >= 0.3 else "FAIL"
        evidence = f"Public methods: {public_methods}, documented: {documented_methods} ({doc_ratio:.0%})"
        if has_type_hints:
            evidence += ", type hints: yes"
        if has_dataclasses:
            evidence += ", dataclasses: yes"

        self.findings.append(Finding(
            dimension="API Surface", dimension_num=5, status=status,
            message=f"Public methods: {public_methods}, documented: {documented_methods} ({doc_ratio:.0%})",
            evidence=evidence,
            severity="WARNING" if status == "FAIL" else "INFO",
            remediation="Add docstrings to public methods and ensure __init__.py exists" if status == "FAIL" else "",
        ))

    def audit_dimension_6_error_recovery(self) -> None:
        """Dimension 6: Error handling, retries, and fallbacks."""
        py_files = self._scan_files()
        has_try_except = False
        has_retry = False
        has_fallback = False
        has_custom_errors = False
        error_files: List[str] = []

        for pf in py_files:
            try:
                content = pf.read_text()
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Try):
                        has_try_except = True
                    if isinstance(node, ast.FunctionDef) and "retry" in node.name.lower():
                        has_retry = True
                    if isinstance(node, ast.ClassDef) and "Error" in node.name:
                        has_custom_errors = True
                if any(x in content for x in ["retry", "backoff", "fallback", "except"]):
                    error_files.append(pf.name)
            except (SyntaxError, UnicodeDecodeError):
                pass

        status = "PASS" if has_try_except else "FAIL"
        evidence = f"Try/except: {has_try_except}, Retry: {has_try_except}, Custom errors: {has_custom_errors}"

        self.findings.append(Finding(
            dimension="Error Recovery", dimension_num=6, status=status,
            message=evidence,
            evidence=f"Error handling in: {error_files[:5]}",
            severity="CRITICAL" if status == "FAIL" else "INFO",
            remediation="Wrap critical paths in try/except with logging and graceful fallback" if status == "FAIL" else "",
        ))

    def audit_dimension_7_integration(self) -> None:
        """Dimension 7: Modules work together."""
        py_files = self._scan_files()
        imports: List[str] = []

        for pf in py_files:
            try:
                content = pf.read_text()
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imports.append(alias.name)
                    if isinstance(node, ast.ImportFrom):
                        if node.module:
                            imports.append(node.module)
            except (SyntaxError, UnicodeDecodeError):
                pass

        local_modules = {f.stem for f in py_files if f.name != "__init__.py"}
        local_imports = [i for i in imports if any(m in i for m in local_modules)]

        status = "PASS" if len(local_imports) >= 2 else "FAIL"
        self.findings.append(Finding(
            dimension="Integration", dimension_num=7, status=status,
            message=f"Local cross-module imports: {len(local_imports)}",
            evidence=f"Unique local imports: {len(set(local_imports))}",
            severity="WARNING" if status == "FAIL" else "INFO",
            remediation="Add cross-module imports showing modules work together" if status == "FAIL" else "",
        ))

    def audit_all(self, dimensions: Optional[List[int]] = None) -> AuditReport:
        """Run audit across specified dimensions (default: all)."""
        self._start_time = time.monotonic()

        audit_fn = {
            1: self.audit_dimension_1_tests,
            2: self.audit_dimension_2_config,
            3: self.audit_dimension_3_telemetry,
            4: self.audit_dimension_4_persistence,
            5: self.audit_dimension_5_api_surface,
            6: self.audit_dimension_6_error_recovery,
            7: self.audit_dimension_7_integration,
        }

        dims = dimensions or list(range(1, 8))
        for d in dims:
            if d in audit_fn:
                audit_fn[d]()

        duration = (time.monotonic() - self._start_time) * 1000

        report = AuditReport(
            target=str(self.target),
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            version=VERSION,
            findings=self.findings,
            duration_ms=duration,
        )
        return report


# ─── CLI ─────────────────────────────────────────────────────────────────────

def format_human_readable(report: AuditReport) -> str:
    """Format report for human consumption."""
    lines = [
        "",
        "=" * 60,
        f"  PRODUCTION READINESS GATE v{VERSION}",
        "=" * 60,
        "",
        f"  Target: {report.target}",
        f"  Time:   {report.timestamp}",
        f"  Scan:   {report.duration_ms:.0f}ms",
        "",
        "-" * 60,
        f"  {'DIMENSION':<20} {'STATUS':<10} {'SEVERITY':<10}",
        "-" * 60,
    ]
    for f in report.findings:
        status_icon = "✓" if f.status == "PASS" else "✗"
        lines.append(f"  {status_icon} {f.dimension:<18} {f.status:<10} {f.severity:<10}")
    lines.append("-" * 60)

    passed = report.passed_count
    total = len(report.findings)
    lines.append(f"  RESULT: {passed}/{total} dimensions PASS")

    if report.gate_status == GateStatus.PASS:
        lines.append("  GATE:   PASS — Delivery authorized")
    else:
        failed = [f for f in report.findings if f.status == "FAIL"]
        lines.append(f"  GATE:   FAIL — {len(failed)} dimension(s) need remediation")
        for f in failed:
            lines.append(f"    [{f.dimension_num}] {f.dimension}: {f.remediation}")

    lines.append("=" * 60)
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=f"Production Readiness Auditor v{VERSION}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --target ./my_project
  %(prog)s --target ./my_project --dimension 1,3,5
  %(prog)s --target ./my_project --format sarif --output report.sarif
  %(prog)s --target ./my_project --ci
        """,
    )
    parser.add_argument("--target", type=str, required=True, help="Directory to audit")
    parser.add_argument("--dimension", type=str, default="all", help="Dimensions (comma-separated or 'all')")
    parser.add_argument("--output", type=str, default=None, help="Output file path")
    parser.add_argument("--format", choices=["json", "sarif", "github-actions", "human"], default="json", help="Output format")
    parser.add_argument("--ci", action="store_true", help="CI mode: human-readable + exit code")
    parser.add_argument("--severity", choices=["INFO", "WARNING", "CRITICAL"], default="WARNING", help="Minimum severity to report")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    args = parser.parse_args()

    target = Path(args.target)
    if not target.is_dir():
        print(f"Error: {target} is not a directory", file=sys.stderr)
        return ExitCode.AUDIT_ERROR

    if args.dimension == "all":
        dims = None
    else:
        try:
            dims = [int(d.strip()) for d in args.dimension.split(",")]
        except ValueError:
            print(f"Error: Invalid dimension format: {args.dimension}", file=sys.stderr)
            return ExitCode.AUDIT_ERROR

    try:
        auditor = ProductionAuditor(str(target), args.severity)
        report = auditor.audit_all(dims)
    except Exception as e:
        print(f"Error during audit: {e}", file=sys.stderr)
        return ExitCode.AUDIT_ERROR

    # Format output
    if args.ci or args.format == "human":
        output = format_human_readable(report)
    elif args.format == "sarif":
        output = json.dumps(report.to_sarif(), indent=2)
    elif args.format == "github-actions":
        output = report.to_github_actions()
    else:
        output = json.dumps(report.to_dict(), indent=2)

    if args.output:
        Path(args.output).write_text(output)
        print(f"Report written to {args.output}")
    else:
        print(output)

    return ExitCode.SUCCESS if report.gate_status == GateStatus.PASS else ExitCode.GATE_FAILED


if __name__ == "__main__":
    sys.exit(main())
