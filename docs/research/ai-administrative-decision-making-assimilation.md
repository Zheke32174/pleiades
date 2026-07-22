# AI Administrative Decision-Making: Implementation Assimilation

## Decision

The research supports strengthening the existing Pleiades executive stack rather than replacing it with a generic planner, reinforcement-learning controller, or model committee. Pleiades already has policy classification, delegated grants, recurrent polycentric deliberation, dissent preservation, signed trust preflight, separated execution, rollback, append-only learning, and constitutional reservation. The implementation therefore adopts only the missing control clusters with the strongest direct evidence and clearest integration path.

## Adopted now

### Runtime assurance / Simplex-style fallback

An independent runtime monitor, bounded invariants, a short validity window, a hazard threshold, and a ready safe controller are required before the judgment can remain eligible. Any failure forces `fallback-only`. The deciding Mind cannot declare its own runtime envelope safe.

### Calibrated abstention

Risk is no longer represented by unconstrained model confidence. A current certificate must identify its calibration method and satisfy minimum sample size, minimum coverage, maximum selective risk, maximum calibration error, and maximum distribution shift. Failure produces `abstain` rather than approval.

### Assumption-based truth maintenance

Every judgment names direct assumptions. The gate resolves transitive dependencies, refuses cycles and dangling references, preserves defeated and unknown assumptions, enforces validity windows, and evaluates explicit nogoods. A defeated premise removes eligibility from dependent decisions without erasing the prior record.

### Bitemporal decision receipts

Valid time, transaction time, evidence cutoff, supersession lineage, and effective decision expiry are recorded separately. Later corrections supersede rather than rewrite history.

### Policy and provenance integration

The new layer binds existing `PolicyDecisionReceipt`, `WorkspaceDeliberationReceipt`, and `TransitionPreflightReceipt` objects by exact digest. It does not create a parallel policy engine, authority registry, or audit chain.

## Held for later

- **DIFC / labelled security** remains a separate high-value security workstream because it requires system-wide label propagation and declassification semantics.
- **Formal verification** remains appropriate for small learned guards or monitor components, not the whole administrative Mind.
- **Causal policy evaluation** remains useful for structured intervention domains with identifiable assumptions and outcome data.
- **POMDP/CMDP and hierarchical RL** remain domain-specific planning options, not the primary governance layer.
- **Multi-agent committees** remain an advisory disagreement surface. They do not replace calibrated abstention, runtime assurance, or policy enforcement.

## Integration boundary

```text
Atlas / epistemic ledger
        -> bounded assumption projection
Policy classifier
        -> exact policy receipt
Recurrent workspace
        -> persistent-Mind deliberation receipt
Operational trust preflight
        -> exact authority and signature receipt
All four
        -> administrative judgment gate
        -> approve | reject | defer | abstain | fallback-only
```

Only `approve` permits the existing pipeline to proceed toward mandate construction. The judgment gate itself constructs no mandate, executes no action, changes no authority, and cannot authorize constitutional or self-expanding behavior.

## Evaluation surface

The reference implementation includes adversarial cases for:

- upstream receipt tampering;
- blocked trust preflight;
- workspace rejection;
- transitive assumption defeat;
- unknown or stale assumptions;
- dependency cycles;
- triggered nogoods;
- insufficient coverage;
- excessive selective risk;
- stale calibration;
- runtime hazard takeover;
- failed safety invariants;
- non-independent monitoring;
- invalid bitemporal ordering;
- supersession preservation.

The golden fixture demonstrates bounded autonomous approval with no contemporaneous operator approval, while preserving a separate decisionless executor and leaving mandate construction and execution unapplied.
