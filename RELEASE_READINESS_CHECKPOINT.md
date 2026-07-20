# Public Release Readiness Checkpoint

This ledger prevents duplicate review work. Reconsider an entry only when its recorded head, CI result, dependency/advisory state, public claim, blocker state, or steward instruction changes.

## pleiades

- **Default branch:** `main`
- **Last reviewed default head:** `ce40d41d3cb712aef20416b1227edb3d19e988f5`
- **Draft branch:** `hardening/public-release-readiness-v1`
- **Checkpoint head before this ledger update:** `5810ce23652ed1a79d05965950d8ba2d6abb389d`
- **Draft PR:** #34 — deterministic lean source distribution
- **Completed scope:** public claims; bounded release contents; deterministic double build; exact Git-blob manifest; SPDX 2.3 inventory; SHA-256 checksums; build receipt; immutable matching-tag release creation; public tree/history sensitivity scan; removal of misleading GHCR package lane; release provenance attestations; immutable-SHA pinning for release-path Actions; non-persistent checkout credentials; required artifact-metadata permission for current `actions/attest` behavior; ordinary current-tree redaction of the catalogued Windows profile identity.
- **Resolved findings:** non-runnable container-package presentation removed; generic release notes replaced with download-first scope language; release refuses mismatched/non-main-reachable tags and refuses mutation of an existing release; generated artifacts are reproducible and checksum-verifiable; release artifacts receive GitHub/Sigstore provenance attestations; release-path third-party Actions no longer rely on movable major-version tags; the current `PLEIADES_STATE.md` no longer publishes the catalogued Windows username/profile path.
- **Open blocker:** issue #42 remains partially open. The ordinary current-tree Windows profile disclosure is redacted, but user-specific paths remain in blobs reachable from the release candidate. They are not credentials or keys. A clean public-history claim still requires an explicitly approved coordinated history rewrite, open-branch rebase plan, and exact post-rewrite rescan.
- **Validation receipts:** ordinary CI run `29740645990` passed at `0d624375efbfb3db5b9be44f17e19d75fa2fa22c`. Public-source run `29740646005` passed parsing, lean invariants, sensitivity capture, deterministic double build, checksum verification, source-boundary receipt verification, and evidence upload; it failed only at the intended final sensitivity gate. At `00008fdc909d91c5247ea3cc33e3dfcc5bc6cb65`, ordinary CI run `29758299761` passed, but public-source run `29758299838` failed inside `actions/checkout` before repository validation. The failure coincided with the newly released v4.4.0 unsafe-PR checkout guard. The release paths now use verified upstream `actions/checkout` v7.0.1 commit `3d3c42e5aac5ba805825da76410c181273ba90b1`, whose release includes a fix for the new guard's default-input path. The bot-authored redaction commit produced `action_required` entries with no jobs; this ledger commit is the exact-head validation trigger.
- **Changed conclusion:** the v4.4.0 full-SHA pin was immutable but not operationally suitable after upstream introduced the new PR safety guard. Fresh upstream release evidence on 2026-07-20 justified advancing only `actions/checkout` to verified v7.0.1. Separately, current-tree redaction is now complete and no longer belongs in the deferred list; only reachable-history removal remains blocked on explicit rewrite authority.
- **Deferred:** full-SHA pinning for the broader non-release CI workflow after trusted identities for every referenced Action are recorded; coordinated Git history rewrite and affected-branch rebase; release/tag publication.
- **Next action:** inspect CI for the head created by this ledger update. Expected healthy behavior is ordinary CI success and public-source execution through deterministic packaging, ending only at the sensitivity gate for retained reachable-history findings. If checkout or packaging fails earlier, repair the concrete workflow defect. Do not rewrite history without separate steward approval.

## mem-watchdog

- **Draft branch:** `fix/nonblocking-red-alerts`
- **Last recorded draft head:** `327ead9ec23a9f61acc295f285e317897ef54317`
- **Draft PR:** #3
- **Completed scope:** nonblocking RED notification delivery, bounded alert worker, hysteresis/cooldown/deduplication, failure containment, regression tests, CI definition.
- **Validation receipt:** Actions run `29709302018` failed before executing any steps; no usable job log or Python-test receipt was produced.
- **Next action:** reconsider only when the branch head or runner result changes.

## fixxy-deck

- **Last completed scope:** exact privileged WebView-origin classification, external-browser routing for nonprivileged HTTP(S), subframe/redirect/restored-state checks, WebView hardening, adversarial Java tests.
- **Next action:** reconsider only on a changed branch head, CI result, public claim, dependency/advisory state, or steward request.

## Comparison provenance

The release branch follows current public-release patterns selectively:

- GitHub artifact attestations bind downloadable artifacts to repository, workflow, event, and commit provenance; attestations supplement rather than replace security review.
- Checksums remain independently downloadable and verifiable.
- Release assets are built from exact reviewed Git blobs rather than a mutable working tree.
- Release-path Actions are pinned to full upstream commit SHAs with human-readable version comments.
- Checkout credentials are not persisted where subsequent authenticated Git operations are unnecessary.
- Dependency review remains a future candidate where supported package manifests make it useful.
- No external project code was copied.

Trusted upstream identities recorded for this checkpoint:

- `actions/checkout` `v7.0.1`: `3d3c42e5aac5ba805825da76410c181273ba90b1`
- `actions/setup-python` `v5.6.0`: `a26af69be951a213d495a4c3e4e4022e16d87065`
- `actions/upload-artifact` `v4.6.2`: `ea165f8d65b6e75b540449e92b4886f43607fa02`
- `actions/attest` `v4.1.1`: `a1948c3f048ba23858d222213b7c278aabede763`
