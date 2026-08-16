# Recurrent Executive Workspace and Emergency Recovery

This tranche implements progression points 41–60 from
`modos/ECOLOGY_PROGRESSION_100.md`.

## Recurrent executive workspace

`workspace.py` closes one recurrent executive cycle into a persistent Mind
decision.

The cycle requires:

- one `mindId`;
- exact proposal, policy, Atlas belief-state, and Forge executive-state digests;
- at least two recurrent rounds;
- independent proposal, risk, policy, and dissent contributions;
- at least three differentiated principals;
- bounded historical competence weighting;
- explicit evidence on every contribution.

No contribution may become the whole Mind. Historical competence can weight a
contribution but is capped so that past success cannot silently monopolize the
workspace. Dissent receives a minimum effective weight and unresolved dissent
is retained across cycles.

The deterministic outcome is `approve`, `reject`, `defer`, or
`request-more-evidence`. Ties defer. The receipt grants no execution authority.

## Emergency and recovery authority

`emergency.py` verifies short-lived emergency containment authority separately
from ordinary executive evolution.

Emergency grants:

- last no longer than one hour;
- permit only containment, isolation, rollback, and evidence preservation;
- cannot alter constitutional policy or expand authority;
- require post-event review and evidence preservation;
- expire automatically.

Continuity state records available Mind components, available nodes, recovery
quorum principals, and revoked grants. Severe partial loss enters safe mode and
requires at least two recovery-quorum principals. Revoked grants are never
rehydrated merely because the system recovered from failure.

The verifier emits an execution-pending receipt. It does not isolate a node,
roll back a service, restore a grant, or mutate canonical state.

## Validation

```bash
python ci/validate-workspace-emergency.py
python modos/governance/test_workspace_emergency.py
```

Locally reproduced:

- seven contract definitions validated;
- two deterministic engines exercised;
- seventeen adversarial tests passed;
- two golden digests reproduced;
- executable files passed bytecode compilation.
