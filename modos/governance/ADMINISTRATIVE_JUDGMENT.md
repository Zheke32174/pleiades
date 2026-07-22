# Administrative Decision and Judgment Layer

## Purpose

This layer closes the gap between cryptographically valid authority and sound autonomous judgment. Existing Pleiades control surfaces already classify policy, bind the persistent Mind, preserve dissent, verify grants and signatures, and stop before mandate construction. The administrative judgment gate adds four missing controls before that boundary may advance:

1. **Assumption-based truth maintenance** — every decision names the assumptions it depends on; transitive dependencies, defeats, stale validity windows, and explicit nogoods are resolved deterministically. A defeated premise retracts eligibility for every dependent decision without deleting history.
2. **Calibrated abstention** — a current risk certificate must meet declared coverage, selective-risk, calibration-error, sample-size, and distribution-shift budgets. Failure produces `abstain`, not a fabricated answer.
3. **Bitemporal decision receipts** — valid time and transaction time remain separate. The receipt records when its claims apply, when they were known, what prior receipt it supersedes, and the earliest expiry across evidence, calibration, and runtime monitoring.
4. **Runtime assurance / Simplex takeover** — an independent monitor verifies bounded invariants and a ready fallback controller. A failed invariant, stale monitor, unavailable fallback, or hazard-threshold breach produces `fallback-only` and revokes mandate-construction eligibility.

## Position in the control path

```text
PolicyDecisionReceipt
        +
WorkspaceDeliberationReceipt
        +
TransitionPreflightReceipt
        +
AdministrativeJudgmentCase
        |
        v
AdministrativeJudgmentReceipt
        |
        +-- approve       -> eligible for mandate construction
        +-- reject        -> authority/signature/policy path rejected
        +-- defer         -> assumptions or upstream deliberation unresolved
        +-- abstain       -> calibrated risk budget not satisfied
        +-- fallback-only -> runtime monitor requires safe-controller takeover
```

The layer does not replace policy-as-code, the authority registry, signed evidence, operational trust preflight, the recurrent workspace, the executor, or the rollback engine. It binds them by exact digest.

## Operator independence

A bounded judgment may be approved with zero contemporaneous operator approvals when promoted policy and the existing authority path allow it. Operator independence is not implemented as absence of control. It is implemented as independently enforced control:

- models contribute but do not individually own the decision;
- the persistent Mind is the decision principal;
- policy remains externally declared and non-self-modifiable;
- the judgment gate cannot broaden grants or policy;
- the runtime monitor is independent of the deciding path;
- the fallback controller must already be ready;
- execution remains a separate decisionless capability;
- constitutional and self-authority changes remain reserved.

## Assumption closure

`requiredAssumptionRefs` defines the direct premises. The gate computes their transitive closure, rejects dependency cycles and dangling references, checks bitemporal currency, and preserves defeated or unknown assumptions as explicit retraction causes. `nogoods` record assumption sets that may not be simultaneously active. Triggering a nogood forces deferral.

This is a bounded ATMS-style mechanism, not an unrestricted theorem prover. It provides dependency-directed rollback and inspectable explanations without pretending that every tacit assumption has already been externalized. The assumption set is a decision-time projection from Atlas and the epistemic-governance ledger; it is not a second canonical belief store and cannot overwrite either source.

## Risk certificates and abstention

The deterministic gate accepts certificates produced by one of three declared methods:

- `conformal-risk-control`;
- `selective-risk-holdout`;
- `calibrated-threshold`.

Statistical fitting remains outside the judgment gate. The gate enforces the resulting certificate against promoted integer-basis-point budgets and refuses stale or shifted certificates. Both risk and coverage must be reported; reducing risk by refusing nearly everything does not count as success.

## Runtime assurance

The runtime snapshot binds an independent monitor identity, fallback-controller identity and readiness, a short validity window, a hazard score and takeover threshold, and explicit invariant checks with evidence digests. Any runtime blocker dominates an otherwise favorable model judgment and produces `fallback-only`.

## Bitemporal receipts

The receipt distinguishes:

- `validFrom` / `validUntil`: when the decision's world-state claims apply;
- `recordedAt`: when the case was recorded;
- `knowledgeCutoffAt`: the newest evidence the judgment was allowed to use;
- `decisionValidUntil`: the earliest expiry among the case, calibration certificate, and runtime monitor;
- `supersedesReceiptDigest`: the prior receipt replaced by this one without erasure.

## Deliberate boundary

The implementation constructs no mandate, executes no action, mutates no policy, grant, registry, Atlas state, Forge state, or canonical ontology, grants no individual model executive sovereignty, and cannot let the Mind enlarge its own authority. An `approve` result means only that the existing mandate-construction path may proceed while every time and evidence binding remains current.
