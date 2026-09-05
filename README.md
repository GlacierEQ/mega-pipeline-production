# APEX Mega-Pipeline: Production

A deterministic 10-phase engineering pipeline that turns any task into elite production code. No evidence = no advancement.

## Pipeline

```
Orient → Grill → Spec → Workspace → Implement → Gate (7d) → Verify → Review → Finalize → Finish
```

## Quick Start

```bash
python3 scripts/pipeline_runner.py --target <your-project> --format markdown
```

## Phases

| # | Phase | Purpose |
|---|-------|---------|
| 1 | Orient | Inspect repository, decide work shape |
| 2 | Grill | Resolve decisions interactively |
| 3 | Spec | Create feature document |
| 4 | Workspace | Prepare environment |
| 5 | Implement | Execute code changes |
| 6 | **Gate** | **7-dimension production audit** |
| 7 | Verify | Run full test suite |
| 8 | Review | Code review |
| 9 | Finalize | Update docs, mark delivered |
| 10 | Finish | Report, suggest next action |

## Production Gate (7 Dimensions)

| # | Dimension | Minimum |
|---|-----------|---------|
| 1 | Tests | pytest suite, >80% coverage |
| 2 | Config | Externalized TOML/YAML |
| 3 | Telemetry | Structured logging + metrics |
| 4 | Persistence | JSONL state snapshots |
| 5 | API Surface | Documented interface |
| 6 | Error Recovery | Retry + fallbacks |
| 7 | Integration | Cross-module imports |

## Structure

```
mega-pipeline-production/
├── SKILL.md                    # Pipeline spec
├── scripts/
│   ├── pipeline_runner.py      # Automated runner
│   └── production_auditor.py   # 7-dimension auditor v2.0.0
├── references/
│   └── remediation.md          # Fix templates
├── utils.py                    # Shared utilities
├── config.py                   # Production config
├── verify_all.py               # Module verification
└── apex_*.py                   # Example production modules
```

## License

APEX Estate — GlacierEQ
