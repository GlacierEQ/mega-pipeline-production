# Frontier Architect → Manager → Worker Execution Pattern

## Pipeline integration
This pattern compounds the existing production pipeline; it does not replace the pipeline or its specialist stages.

### Frontier opening pass
Before mass implementation, the strongest available frontier model acts as architect **and executor**:
- recover source-bearing/live state
- preserve the full Operator mission
- identify the highest-leverage implementation slice
- directly build/repair that slice
- test it and verify readback
- extract a golden implementation and executable blueprint
- emit manager, worker, evidence, escalation, and final-repair contracts

The frontier model must make the high-leverage structure real. A plan or audit alone is insufficient.

### Manager execution layer
Manager-class models instantiate the frontier blueprint across workstreams. They coordinate workers, preserve invariants, compare results to the golden implementation, repair routine drift/failures, reconcile outputs, and escalate only genuinely architectural exceptions.

### Worker execution layer
Worker-class models/capabilities execute coherent work units in parallel. Every work unit returns objective, action, change/output, source/evidence, tests/readback, receipt/durable identifier where available, confidence, contradictions, and deviations.

Use the least expensive worker capable of reliably satisfying the contract. Escalate capability based on demonstrated insufficiency, not habit.

### Manager reconciliation
Managers merge verified gains, resolve routine conflicts, run integration checks, repair ordinary defects, and prepare actual source-bearing resulting state for the frontier final pass.

### Frontier final execution pass
The frontier model returns to the real implementation and:
- inspects actual outputs and provider/tool state
- compares them to mission, golden implementation, and blueprint
- runs hard/adversarial tests
- directly repairs remaining high-complexity defects
- resolves cross-system contradictions
- upgrades materially weak areas
- re-tests and verifies final state

The final frontier pass is an execution/repair pass, not a recommendation or acceptance memo.

## Quality objective
Default substantive-work target: 9.0+ across mission fidelity, correctness, completeness, evidence, implementation, integration, recoverability, and verified state.

A quality shortfall triggers additional repair/cognition automatically. It is not converted into a report for the Operator to manually route.

## Pipeline mapping
Existing stages remain useful specialist projections. The orchestration pattern spans them:

`Frontier establish reality → Orient/Spec → golden implementation → Workspace/Implement → manager/worker scale → Verify/Review → manager reconciliation/repair → Frontier finish reality → Finalize/Finish`

Where legacy stage names or gates imply permission rather than quality/evidence semantics, do not infer an Operator-approval requirement. Verification is active testing/readback/repair and must not become a substitute for execution.

## Composition rule
Merge and strengthen. Preserve working specialist capabilities and route through them; do not replace the estate with a new monolith or duplicate specialist ownership.
