# Public Release Readiness Checkpoint

This ledger prevents duplicate review work. Reconsider an entry only when its recorded head, CI result, dependency/advisory state, public claim, blocker state, or steward instruction changes.

## pleiades

- **Default branch:** `main`
- **Last reviewed default head:** `ce40d41d3cb712aef20416b1227edb3d19e988f5`
- **Draft branch:** `hardening/public-release-readiness-v1`
- **Checkpoint head:** `248a4c25b5b622b350848b41aaaa77c4552d8244`
- **Draft PR:** #34 — deterministic lean source distribution
- **Completed scope:** public claims; bounded release contents; deterministic double build; exact Git-blob manifest; SPDX 2.3 inventory; SHA-256 checksums; build receipt; immutable matching-tag release creation; public tree/history sensitivity scan; removal of misleading GHCR package lane; release provenance attestations.
- **Resolved findings:** non-runnable container-package presentation removed; generic release notes replaced with download-first scope language; release refuses mismatched/non-main-reachable tags and refuses mutation of an existing release; generated artifacts are reproducible and checksum-verifiable; release artifacts now receive GitHub/Sigstore provenance attestations.
- **Open blocker:** issue #42. Current tree and reachable public history contain user-specific workstation paths. They are not credentials or keys, but the release must remain blocked until current-tree redaction and an explicitly approved coordinated history rewrite/rebase/rescan are complete.
- **Validation receipts:** ordinary CI run `29710071027` passed at `df9a3211d3dd07f18aa8631fcba3d287e0783293`; public-source run `29710071025` completed deterministic packaging and receipt verification, then failed only at the intended sensitivity gate. The new attestation change at `248a4c25b5b622b350848b41aaaa77c4552d8244` requires a fresh CI receipt.
- **Deferred:** full-SHA pinning for third-party Actions after recording trusted upstream commit identities; current-tree redaction of the large historical state document; coordinated Git history rewrite; release/tag publication.
- **Next action:** inspect CI for checkpoint head `248a4c25b5b622b350848b41aaaa77c4552d8244`; repair any workflow defect; then redact current-tree workstation identities without authorizing or performing history rewrite.

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

The release branch follows current GitHub public-release patterns selectively:

- artifact attestations bind downloadable artifacts to repository, workflow, event, and commit provenance;
- checksums remain independently downloadable and verifiable;
- release assets are built from exact reviewed Git blobs rather than a mutable working tree;
- dependency review remains a future candidate where supported package manifests make it useful;
- no external project code was copied.
