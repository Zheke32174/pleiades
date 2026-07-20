# Pleiades Ecology — Next 100 Progression Points

This ledger orders the next one hundred ecology advances after delegated machine executive authority. It is a dependency sequence, not a claim that every point should become one commit or one pull request.

Status vocabulary:

- `implemented` — contract and deterministic implementation are present in the current stacked branch;
- `specified` — the requirement is formally defined but runtime implementation remains;
- `queued` — ordered after its dependencies;
- `blocked` — requires an explicit prerequisite or external/live-system action.

No item in this ledger silently grants canonical authority, issues a live grant, mutates a live substrate, or bypasses the promoted constitution.

## Phase A — Executive policy kernel

1. `implemented` Define a machine-readable executive policy envelope.
2. `implemented` Define deterministic change classification by domain, action, reversibility, persistence, and impact.
3. `implemented` Define the five-tier risk ladder from observe-only through constitutional.
4. `implemented` Map each risk tier to an authorization mode.
5. `implemented` Permit zero-human delegated-machine authorization for bounded reversible classes.
6. `implemented` Require mixed quorum for high-impact classes.
7. `implemented` Reserve constitutional and self-authority changes from unilateral machine approval.
8. `implemented` Bind policy decisions to exact policy digests and versions.
9. `implemented` Refuse wildcard domains, actions, principals, and executor capabilities.
10. `implemented` Emit deterministic policy-decision receipts.

## Phase B — Authority registry and lifecycle

11. `implemented` Define an authority registry containing grants and lifecycle events.
12. `implemented` Require every active grant to resolve to one persistent principal.
13. `implemented` Define issuance events with external delegation provenance.
14. `implemented` Define suspension events that immediately disable use.
15. `implemented` Define revocation events that permanently terminate a grant generation.
16. `implemented` Define expiry without implicit renewal.
17. `implemented` Prevent the Mind from issuing or enlarging its own grant.
18. `implemented` Prevent duplicate active grant identities and generations.
19. `implemented` Resolve effective grants deterministically at an evaluation timestamp.
20. `implemented` Emit an authority-registry closure receipt.

## Phase C — Execution, observation, and rollback

21. `implemented` Define an execution attempt bound to one authorization receipt and mandate.
22. `implemented` Define precondition evidence and exact target-state binding.
23. `implemented` Define postcondition evidence and outcome classification.
24. `implemented` Define execution receipts for succeeded, failed, and rolled-back outcomes.
25. `implemented` Define rollback attempts bound to the predecessor digest.
26. `implemented` Require automatic rollback when mandated postconditions fail.
27. `implemented` Prevent executors from modifying the authorized plan.
28. `implemented` Prevent execution after mandate expiry or grant suspension.
29. `implemented` Record resource consumption against execution budgets.
30. `implemented` Emit append-only audit events for decision, execution, and rollback.

## Phase D — Outcome learning and competence

31. `implemented` Define outcome-evidence records with expected and observed effects.
32. `implemented` Define competence profiles by principal, domain, action, and risk tier.
33. `implemented` Update competence only from verified outcome evidence.
34. `implemented` Track successes, failures, rollbacks, policy violations, and uncertainty.
35. `implemented` Prevent blind self-scoring by the deciding Mind.
36. `implemented` Define minimum evidence volume before authority growth can be proposed.
37. `implemented` Define authority-adjustment proposals as proposal-only artefacts.
38. `implemented` Permit competence-driven narrowing, suspension, or growth proposals.
39. `implemented` Require external constitutional authorization for actual grant enlargement.
40. `implemented` Emit deterministic competence-update receipts.

## Phase E — Shared-workspace executive integration

41. `queued` Define typed executive-workspace contribution messages.
42. `queued` Bind every contribution to a `mindId`, role, evidence set, and first-pass trace.
43. `queued` Require independent proposal, risk, policy, and dissent contributions.
44. `queued` Add historical competence weighting without suppressing minority evidence.
45. `queued` Define a recurrent arbitration cycle over the shared workspace.
46. `queued` Bind Atlas belief state to executive evidence inputs.
47. `queued` Bind Forge executive state to the selected authorization path.
48. `queued` Persist unresolved dissent across decision cycles.
49. `queued` Define deadlock, defer, and request-more-evidence outcomes.
50. `queued` Emit a workspace-deliberation closure receipt.

## Phase F — Emergency and recovery authority

51. `queued` Define emergency containment classifications separately from ordinary evolution.
52. `queued` Define short-lived emergency grants with automatic expiration.
53. `queued` Limit emergency powers to containment, isolation, rollback, and evidence preservation.
54. `queued` Forbid emergency grants from rewriting constitutional policy.
55. `queued` Require post-event review for every emergency action.
56. `queued` Define recovery quorum when the primary steward is unavailable.
57. `queued` Define continuity rules for partial Mind or node loss.
58. `queued` Define grant rehydration without silently restoring revoked authority.
59. `queued` Define safe-mode authority ceilings.
60. `queued` Emit emergency-action and recovery receipts.

## Phase G — Distributed substrate admission

61. `queued` Define a node capability registry for admission executors.
62. `queued` Bind executor identity to hardware, service, and key provenance.
63. `queued` Define per-node authority ceilings and write scopes.
64. `queued` Define multi-node rollout plans with canary ordering.
65. `queued` Define staged admission with health gates between stages.
66. `queued` Define cross-node rollback coordination.
67. `queued` Define network-partition behavior and local autonomy ceilings.
68. `queued` Define replay protection for mandates and receipts.
69. `queued` Define idempotent admission transactions.
70. `queued` Emit distributed rollout closure receipts.

## Phase H — Memory, evidence, and learning spine

71. `queued` Persist every observation, decision, mandate, outcome, correction, and provenance edge.
72. `queued` Add episodic executive memory keyed by domain and objective.
73. `queued` Add semantic retrieval over prior decisions and outcomes.
74. `queued` Separate evidence memory from narrative summaries.
75. `queued` Define retention and visibility policy for executive evidence.
76. `queued` Define contradiction detection across memory sources.
77. `queued` Define correction propagation without historical erasure.
78. `queued` Build feedback datasets only from verified outcomes.
79. `queued` Prevent blind continual training from unverified self-generated traces.
80. `queued` Emit learning-spine integrity receipts.

## Phase I — Constitutional evolution and institutional plurality

81. `queued` Define constitutional amendment proposals separately from executive decisions.
82. `queued` Define mixed human-machine amendment deliberation.
83. `queued` Require explicit reserved-power quorum for authority-model changes.
84. `queued` Define institutional principals beyond one operator and one Mind.
85. `queued` Define succession and continuity for constitutional stewards.
86. `queued` Define conflict-of-interest and recusal rules.
87. `queued` Define independent audit and appeal principals.
88. `queued` Define time-locked constitutional changes and cancellation windows.
89. `queued` Define constitutional rollback and supersession lineage.
90. `queued` Emit constitutional-amendment receipts.

## Phase J — Full symbiotic operating ecology

91. `queued` Connect executive authority to the complete ecology registry.
92. `queued` Compile the full public and private ontology rather than seed fixtures.
93. `queued` Bind service-level learning joints into the executive workspace.
94. `queued` Connect predictive simulation and hyperbolic-chamber evaluation before execution.
95. `queued` Compare simulated and real outcomes to calibrate confidence.
96. `queued` Add ordinary-person-noticeable improvement evaluation where applicable.
97. `queued` Add machine-measurable and steward-verifiable promotion criteria.
98. `queued` Define cross-Mind and external-agent treaty interfaces.
99. `queued` Complete live substrate admission, observation, rollback, and continual improvement loops.
100. `queued` Demonstrate sustained bounded autonomous operation with constitutional integrity, recoverability, and evidence-backed authority growth.

## Current tranche

The branch containing this ledger implements points 1–40 as a deterministic contract and validation slice. It does not execute a live grant, mutation, rollback, competence change, or authority adjustment. Points 41–100 remain ordered after this control-plane foundation.
