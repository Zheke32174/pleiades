# Pleiades implementation audit and outstanding-work ledger

Date: 2026-07-19  
Last reconciled: 2026-07-20

## Purpose

This file is the durable bridge between architecture/review sessions and repository state. It records work that was discussed, discovered, partially implemented, implemented on an unmerged branch, or fully verified.

A conversational note is not a project record. Anything still outstanding must exist here, in a repository issue, or in a pull request with an explicit remaining-work statement.

## Completion semantics

Use these states consistently:

- **VERIFIED COMPLETE** — merged/default-branch code or documentation exists and the claimed runtime, package, release, or artifact result was actually verified.
- **IMPLEMENTED, NOT PROMOTED** — code exists in an open branch or pull request but has not reached the default branch or durable release surface.
- **RECORDED, NOT IMPLEMENTED** — the requirement exists in an issue, PR body, or this ledger, but executable work remains.
- **BLOCKED EXTERNALLY** — repository work is ready but an account, provider, hardware, credential, or policy boundary prevents verification.
- **NEEDS RE-AUDIT** — prior sessions reported a result, but the current pass could not independently retrieve the final evidence.

Workflow YAML by itself does not prove a build or release. A release is complete only when the intended downloadable asset and verification material are actually present and retrievable.

## Confirmed implemented on default branches

### Attribution and public-release documentation

- `Zheke32174/pleiades/CREDITS.md` exists and records third-party projects, organizations, licenses, usage, vendoring, modification, and local-path handling.
- `Zheke32174/pleiades-container/CREDITS.md` exists with the same attribution contract for the container substrate.
- `Zheke32174/pleiades/tools/TOOL-FRAMEWORK.md` now links to `../CREDITS.md`; the retired absolute workspace reference is no longer the accreditation pointer.

### GitHub Actions noise containment

The July 19 workflow-containment pass implemented the following:

- quarantined duplicated high-frequency relay runners;
- quarantined scheduled model-triage workflows;
- quarantined automatic model event dispatch in legacy repositories;
- removed ambient schedules from identified private maintenance workflows;
- intent-gated broad private CI workflows behind `ci/**`, `release/**`, or manual dispatch;
- replaced release-on-every-default-branch-push workflows with tag/manual release contracts;
- separated Android build intent from release publication intent;
- corrected the remaining broad private backup trigger.

The account-level reason private GitHub-hosted Actions were previously rejected before job execution remains unresolved. It is owned durably by Pleiades issue #38.

### Audit preservation

This ledger was committed so session discoveries and implementation state no longer depend on conversation history. Repository-local release-status records were also added to the relevant application repositories.

## Android application estate

### Yojimbo

State: **IMPLEMENTED, NOT PROMOTED**

Durable records exist across the stacked Yojimbo pull requests. One reviewed branch produced a successful assembled engineering-preview APK in GitHub Actions. The release machinery remains stacked behind the runtime PR chain and is not yet merged to the default branch. Durable Releases-page publication remains pending.

Completion requires:

1. resolve/rebase and merge the stacked runtime chain in order;
2. merge the engineering-preview release work;
3. run the default-branch release path;
4. verify the actual Release asset, checksum, source identity, package identity, and signing posture.

### Recall applications

State: **VERIFICATION INTENT OPEN; BUILD NOT YET VERIFIED**

Repository-local completion contracts and draft non-publishing build-verification PRs exist. They deliberately do not claim that an APK exists. Completion requires actual package, run, checksum, signing, artifact, and download evidence.

### Other Android repositories

Prior sessions reported durable Releases across public and private Android repositories. That claim remains **NEEDS RE-AUDIT** until a current release-asset inventory is captured in GitHub-accessible evidence. Do not infer completion from workflow files or old notifications.

## Existing durable cross-repository backlog

The following requirements already exist on GitHub and are therefore not trapped only in conversation history.

### Estate-wide review

- Pleiades issue #4 — cross-repository review and modernization program.

### PDK continuity and ingress

- Pleiades issue #16 — durable collision-safe controller event acknowledgements.
- Pleiades issue #17 — durable heartbeat replay and observation continuity.
- Pleiades issue #19 — unified authenticated observation ingress across adapters.
- Pleiades PR #20 — shared observation-ingress batches, receipts, and stream continuity.
- Pleiades PR #21 — cross-repository hardening checkpoint.
- Pleiades PR #22 — immutable Factory review-eligibility contract.
- Pleiades PR #23 — durable controller event continuity.
- Pleiades PR #24 — durable heartbeat continuity.
- Pleiades issue #25 — current-observation reads and boot-epoch retention.

### Factory evidence and source provenance

- Private Factory issues and PRs preserve immutable evidence, orphan-observation recovery, synchronization locks, and honest source identity work.
- Executable patches that cannot yet run because private hosted jobs expose no steps remain recorded as executable but externally blocked, not implemented.

### Host and edge adapters

- Container, Termux, Windows, and Connect pull requests preserve transactional host binding, live-state confinement, typed lifecycle argv, and signed short-lived route assertions.
- Claims of verification remain bound to exact commits and workflow evidence where available.

### Distribution and release hardening

- Factory Stack, Termux, Windows, and Container pull requests preserve deterministic source release, retention, licensing, installability, and reviewability work.

### Inheritance and repository containment

- Undergrowth pull requests preserve explicit inheritance profiles, receipts, and inert default bootstrap behavior.

## Outstanding work that was previously easy to mistake for implementation

1. **Release workflow present, but no release asset verified.** A workflow file is not a package.
2. **Open PR exists, but change is not on the default branch.** The stacked Pleiades/MODOS graph must not be described as merged implementation.
3. **Issue specifies a repair, but executable code has not landed.** Exact patches remain narrower than runtime implementation.
4. **Actions failure noise was contained, but the private Actions account restriction was not diagnosed at the account policy layer.** Issue #38 owns that work.
5. **Prior release counts require a current asset inventory.** Do not preserve remembered numbers as fact without retrievable evidence.
6. **Live-hardware validations remain separate from repository CI.** They cannot be completed by repository edits alone.

## Implementation order

1. Keep every newly discovered gap durable in an issue, PR, exact patch, or this ledger before ending a review session.
2. Finish exact, narrow correctness repairs on already-reviewed PR stacks before opening broad new implementation waves.
3. Apply and validate preserved private repairs when a verified execution surface is available.
4. Produce and retain exact-commit package outputs through the relevant build-verification PRs.
5. Merge and publish reviewed engineering-preview stacks only after evidence gates pass.
6. Resolve issue #38 and run one private canary from each workflow family.
7. Capture machine-readable release/artifact inventories rather than relying on remembered counts.
8. Continue issue #4 repository-by-repository with explicit dispositions: canonical, active-supporting, upstream/reference, archive, or delete candidate.

## Rule for future sessions

Before claiming a task is finished, record all four identities where applicable:

- repository and default-branch commit;
- pull request or issue that owns the change;
- workflow run/test evidence;
- durable artifact or Release asset identity.

When any identity is absent, state the narrower truth: recorded, implemented on a branch, built as an artifact, or verified complete.
