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
- `Zheke32174/pleiades/tools/TOOL-FRAMEWORK.md` now links to `../CREDITS.md`; the retired absolute `/workspaces/gentoo/CREDITS.md` reference is no longer the accreditation pointer.

### GitHub Actions noise containment

The July 19 workflow-containment pass implemented the following:

- quarantined the duplicated five-minute Understory relay runners;
- quarantined the two hourly Gemini scheduled-triage workflows;
- quarantined automatic Gemini event dispatch in both Underhall repositories;
- removed ambient schedules from the identified private maintenance workflows;
- intent-gated broad private CI workflows behind `ci/**`, `release/**`, or manual dispatch;
- replaced release-on-every-default-branch-push workflows with tag/manual release contracts;
- separated Android build intent from release publication intent in the Recall workflows;
- corrected `purple-team-polyglot-backup-wslbak/.github/workflows/ci.yml`, the one broad trigger that had remained after the earlier pass.

The account-level reason private GitHub-hosted Actions were previously rejected before job execution remains unresolved. It is now owned durably by Pleiades issue #38:

`https://github.com/Zheke32174/pleiades/issues/38`

### Audit preservation

This ledger was committed to the Pleiades default branch so that session discoveries and implementation state no longer depend on conversation history.

Repository-local release-status records were also added to:

- `Zheke32174/recall-xed-editor-c8278404e4/RELEASE-STATUS.md`;
- `Zheke32174/recall-underward-d0ccef5ee4/RELEASE-STATUS.md`.

## Android application estate

### Yojimbo

State: **IMPLEMENTED, NOT PROMOTED**

Durable records:

- PR #2: `https://github.com/Zheke32174/understory-yojimbo/pull/2`
- PR #3: `https://github.com/Zheke32174/understory-yojimbo/pull/3`
- PR #4: `https://github.com/Zheke32174/understory-yojimbo/pull/4`
- PR #6: `https://github.com/Zheke32174/understory-yojimbo/pull/6`

PR #6 produced a successful assembled engineering-preview APK in GitHub Actions. The APK existed as an unexpired artifact during the July 19 verification pass. The release machinery remains stacked behind the runtime PR chain and is not yet merged to the default branch. A durable Releases-page publication therefore remains pending.

Completion requires:

1. resolve/rebase and merge the stacked runtime chain in order;
2. merge the engineering-preview release work;
3. run the default-branch release path;
4. verify the actual Release asset, checksum, source identity, package identity, and signing posture.

### Recall Xed Editor

State: **VERIFICATION INTENT OPEN; BUILD NOT YET VERIFIED**

Repository: `https://github.com/Zheke32174/recall-xed-editor-c8278404e4`

Durable records:

- repository-local completion contract: `RELEASE-STATUS.md`;
- build-verification branch: `ci/verify-apk-20260719`;
- draft PR #1: `https://github.com/Zheke32174/recall-xed-editor-c8278404e4/pull/1`.

The branch contains only a non-publishing CI intent marker. This audit has not yet retrieved a completed package from a durable Release or current Actions artifact, so no APK claim is made.

Completion requires retained exact-commit package output, checksum, package/signing record, workflow-run identity, artifact identity, and a verified durable Release when publication is intended.

### Recall Underward

State: **VERIFICATION INTENT OPEN; BUILD NOT YET VERIFIED**

Repository: `https://github.com/Zheke32174/recall-underward-d0ccef5ee4`

Durable records:

- repository-local completion contract: `RELEASE-STATUS.md`;
- build-verification branch: `ci/verify-apks-20260719`;
- draft PR #1: `https://github.com/Zheke32174/recall-underward-d0ccef5ee4/pull/1`.

The branch contains only a non-publishing CI intent marker. This audit has not yet retrieved the expected package set from a durable Release or current Actions artifact, so no APK-set claim is made.

Completion requires retention of every expected package output and checksum, expected-versus-produced inventory, package/signing records, exact-commit provenance, workflow-run identity, artifact identity, and verification of a durable Release when publication is intended.

### Other Android repositories

Prior sessions reported 27 durable Releases across the public and private Android repositories. That claim remains **NEEDS RE-AUDIT** until a current release-asset inventory is captured in GitHub-accessible evidence. Do not infer completion from workflow files or old notifications.

## Existing durable cross-repository backlog

The following requirements already exist on GitHub and are therefore not trapped only in conversation history.

### Estate-wide review

- Pleiades issue #4 — cross-repository review and modernization program:
  `https://github.com/Zheke32174/pleiades/issues/4`

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

- `pleiades-factory` issue #4 and PR #5 — immutable, content-addressed evidence generations.
- `pleiades-factory` issue #6 — **RECORDED, NOT IMPLEMENTED**. The exact code-and-test repair is preserved on PR #5 at `patches/issue-6-orphan-observation-recovery.patch`; applying and validating it remains blocked by private hosted jobs that allocate no executable steps.
- `pleiades-factory-stack` issue #5 and PR #6 — transactional locks and honest dirty-source identity.
- `pleiades-factory-stack` issue #7 — serialize synchronization and bind state to one checkout generation.

### Host and edge adapters

- `pleiades-container` issue #8 and PR #9 — transactional host binding and ambient nspawn-settings refusal.
- `pleiades-container` issue #10 — **IMPLEMENTED, NOT PROMOTED** on PR #9. The branch performs a compensating `daemon-reload`, preserves both failure results, reports manager uncertainty on double failure, and includes deterministic tests; CI run `29709096507` passed.
- `pleiades-termux` issue #3 and Pleiades issue #19 — authenticated delivery/acknowledgement design.
- `pleiades-termux` PR #5 — delivery-stream continuity without transport.
- `pleiades-termux` issue #6 — **IMPLEMENTED, NOT PROMOTED** on PR #5. Live state is confined to `PLEIADES_ROOT`; symlinked roots, state, queue, and locks are refused; managed-object ownership and file identity are rechecked; external operator exports remain supported. Full CI and reproducible source-package run `29709629604` passed at head `113168429284a676007cb53b440081796c1e22b8`.
- `pleiades-windows` PR #6 — typed canonical WSL lifecycle argv and shell-injection removal.
- `pleiades-connect` PR #3 — signed short-lived SSH route assertions.

### Distribution and release hardening

- `pleiades-factory-stack` PR #4 — deterministic tagged source release, checksums, SPDX inventory, and exact-commit receipt.
- `pleiades-termux` PR #4 — honest source release, retention, licensing, and removal controls.
- `pleiades-windows` PR #4 — installable/distributable observer contract.
- `pleiades-container` PR #6 — distributable and reviewable container substrate.

### Inheritance and repository containment

- `undergrowth` PR #27 — explicit inheritance profiles, receipts, and inert default bootstrap.

## Outstanding work that was previously easy to mistake for implementation

1. **Release workflow present, but no release asset verified.** Applies currently to Yojimbo, Recall Xed, and Recall Underward until evidence says otherwise.
2. **Open PR exists, but change is not on the default branch.** The stacked Pleiades/MODOS PR graph must not be described as merged implementation.
3. **Issue specifies a repair, but executable code has not landed.** Pleiades issue #25, Factory issue #6, and Factory Stack issue #7 are current examples. Factory issue #6 has an exact patch preserved, but the patch itself is not runtime implementation.
4. **Actions failure noise was contained, but the private Actions account restriction was not diagnosed at the account banner/billing/policy layer.** Pleiades issue #38 now owns that work.
5. **Prior release counts require a current asset inventory.** Do not preserve old numbers as fact without retrievable evidence.
6. **Live-hardware validations remain separate from repository CI.** Pleiades issue #6 owns Alienware/Lenovo capability-lease validation and cannot be completed by repository edits alone.

## Implementation order

1. Keep every newly discovered gap durable in an issue, PR, exact patch, or this ledger before ending a review session.
2. Finish exact, narrow correctness repairs on already-reviewed PR stacks before opening broad new implementation waves.
3. Apply and validate the preserved Factory issue #6 patch once private Actions execute real steps or another verified execution surface is available.
4. Produce and retain verified Xed and Underward Android build outputs through draft PRs #1 in their respective repositories.
5. Merge and publish the Yojimbo engineering-preview stack after review.
6. Resolve Pleiades issue #38 and run one private canary from each workflow family.
7. Capture a machine-readable Android release/artifact inventory rather than relying on remembered counts.
8. Continue Pleiades issue #4 repository-by-repository with explicit dispositions: canonical, active-supporting, upstream/reference, archive, or delete candidate.

## Rule for future sessions

Before claiming a task is finished, record all four identities where applicable:

- repository and default branch commit;
- pull request or issue that owns the change;
- workflow run/test evidence;
- durable artifact or Release asset identity.

When any identity is absent, state the narrower truth: recorded, implemented on a branch, built as an artifact, or verified complete.
