# Pleiades implementation audit and outstanding-work ledger

Date: 2026-07-19

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

The account-level reason private GitHub-hosted Actions were previously rejected before job execution remains an external/account-state question and is not considered solved by trigger containment.

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

State: **RECORDED, NOT VERIFIED**

Repository: `https://github.com/Zheke32174/recall-xed-editor-c8278404e4`

The repository contains Android build and release workflows, but this audit has not verified a completed package in a durable Release, a current Actions artifact, or a committed binary path.

Completion requires an explicit CI/release-intent run, retained exact-commit package output, checksum, package/signing record, and a verified durable Release when publication is intended.

### Recall Underward

State: **RECORDED, NOT VERIFIED**

Repository: `https://github.com/Zheke32174/recall-underward-d0ccef5ee4`

The repository contains the Android suite and release workflow, but this audit has not verified completed package outputs in a durable Release, a current Actions artifact, or committed binary paths.

Completion requires an explicit CI/release-intent run, retention of every expected package output and checksum, exact-commit provenance, and verification of a durable Release when publication is intended.

### Other Android repositories

Prior sessions reported 27 durable Releases across the public and private Android repositories. That claim must be treated as **NEEDS RE-AUDIT** until a current release-asset inventory is captured in GitHub-accessible evidence. Do not infer completion from workflow files or old notifications.

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
- `pleiades-factory` issue #6 — recovery of an observation committed before index publication.
- `pleiades-factory-stack` issue #5 and PR #6 — transactional locks and honest dirty-source identity.
- `pleiades-factory-stack` issue #7 — serialize synchronization and bind state to one checkout generation.

### Host and edge adapters

- `pleiades-container` issue #8 and PR #9 — transactional host binding and ambient nspawn-settings refusal.
- `pleiades-container` issue #10 — compensate systemd manager state after reload failure.
- `pleiades-termux` issue #3 and Pleiades issue #19 — authenticated delivery/acknowledgement design.
- `pleiades-termux` PR #5 — delivery-stream continuity without transport.
- `pleiades-termux` issue #6 — symlink-safe state and lock handling.
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
3. **Issue specifies a repair, but no code has landed.** Issues #25, container #10, Factory #6, Factory Stack #7, and Termux #6 are examples.
4. **Actions failure noise was contained, but the private Actions account restriction was not diagnosed at the account banner/billing/policy layer.**
5. **Prior release counts require a current asset inventory.** Do not preserve old numbers as fact without retrievable evidence.
6. **Live-hardware validations remain separate from repository CI.** Pleiades issue #6 owns Alienware/Lenovo capability-lease validation and cannot be completed by repository edits alone.

## Implementation order

1. Keep every newly discovered gap durable in an issue, PR, or this ledger before ending a review session.
2. Finish exact, narrow correctness repairs on already-reviewed PR stacks before opening broad new implementation waves.
3. Produce and retain verified Xed and Underward Android build outputs.
4. Merge and publish the Yojimbo engineering-preview stack after review.
5. Resolve the private Actions account restriction and run one canary from each workflow family.
6. Capture a machine-readable Android release/artifact inventory rather than relying on remembered counts.
7. Continue Pleiades issue #4 repository-by-repository with explicit dispositions: canonical, active-supporting, upstream/reference, archive, or delete candidate.

## Rule for future sessions

Before claiming a task is finished, record all four identities where applicable:

- repository and default branch commit;
- pull request or issue that owns the change;
- workflow run/test evidence;
- durable artifact or Release asset identity.

When any identity is absent, state the narrower truth: recorded, implemented on a branch, built as an artifact, or verified complete.
