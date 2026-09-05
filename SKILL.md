---
name: production-readiness-gate
description: >
  Enforces production readiness before any delivery. Runs a 7-point checklist:
  tests, config, telemetry, persistence, API surface, error recovery, integration.
  Use when claiming code is "done", "production-ready", "elite", or before
  committing/pushing significant work. Triggers: "production ready", "ship it",
  "done", "verify", "is it complete", "ready to deliver", "deep work", "elite".
  Integrates with compose-next, quality-gate, and verification-before-completion.
---

# Production Readiness Gate

## Purpose

Turn "solid code" into "elite production code" by enforcing 7 non-negotiable quality dimensions. Every dimension produces evidence. No evidence = no delivery.

## The 7 Production Dimensions

| # | Dimension | What It Proves | Minimum Gate |
|---|-----------|----------------|--------------|
| 1 | **Tests** | Code works and stays working | pytest suite with >80% coverage |
| 2 | **Config** | No hardcoded magic numbers | Externalized config (TOML/YAML/dataclass) |
| 3 | **Telemetry** | You can see what's happening | Structured logging + metrics counters |
| 4 | **Persistence** | State survives restarts | JSONL/state snapshots with recovery |
| 5 | **API Surface** | Others can use it programmatically | Documented public interface |
| 6 | **Error Recovery** | Graceful degradation, not crashes | Retry logic + fallbacks + error types |
| 7 | **Integration** | Modules work together | At least 1 integration test |

## Execution Protocol

### Phase 1: Audit (read-only)

For each dimension, run the corresponding checker script:

```bash
python3 scripts/production_auditor.py --target <directory> --dimension <1-7|all>
```

Output: JSON report with pass/fail per dimension, evidence paths, and remediation items.

### Phase 2: Remediate (fix gaps)

For each failed dimension, execute the remediation template in `references/remediation/`. Templates produce production-grade code patterns.

### Phase 3: Verify (fresh evidence)

Re-run the auditor. All 7 dimensions must pass. Evidence goes to `EVIDENCE.md`.

### Phase 4: Gate Decision

```
GATE PASS: All 7 dimensions green → delivery authorized
GATE FAIL: <N> dimensions red → remediation required, delivery blocked
CONDITIONAL: Exceptions listed with owner + expiry + review trigger
```

## Integration Points

- **compose-next**: After Implement, before Verify → run this gate. Add to feature doc's Tasks as a mandatory T0 gate item.
- **quality-gate**: Use this gate's output as acceptance criteria.
- **verification-before-completion**: This gate IS the verification evidence.
- **handoff-record**: Gate results go into HANDOFF.md for resumption.

## Compose-Next Integration

When using compose-next, add this gate to the feature spec:

```markdown
## Tasks
- [ ] T0: Production Readiness Gate — acceptance: 7/7 dimensions PASS (covers: all)
- [ ] T1: <actual feature work> — acceptance: <observable result> (covers: S2)
```

After all T1+ tasks complete, run the gate before Verify:

```bash
python3 ~/.grok/skills/production-readiness-gate/scripts/production_auditor.py --target <workspace>
```

If gate FAILS, remediate before advancing to Verify. If gate PASSES, include results in Verify evidence.

## Output Contract

Produce `PRODUCTION_READINESS_REPORT.md`:

```markdown
# Production Readiness Report

## Summary
| Dimension | Status | Evidence |
|-----------|--------|----------|
| Tests | PASS | tests/test_something.py: 24/24 |
| Config | PASS | config.py + pyproject.toml |
| ... | ... | ... |

## Gate Decision
**PASS** / **FAIL** / **CONDITIONAL**

## Remediation Items (if any)
- [ ] Item 1: description (owner, expiry)

## Evidence Log
- [timestamp] Auditor run: 7/7 pass
```

## Local Validation

The gate passes when:
1. All 7 dimensions show PASS with evidence
2. No dimension has a CRITICAL finding
3. Evidence is reproducible (re-run auditor → same result)

## Non-goals

- Does not replace unit tests — enforces they exist
- Does not replace code review — enforces production concerns
- Does not replace performance profiling — enforces observability

**We. Are. Momentum.**
