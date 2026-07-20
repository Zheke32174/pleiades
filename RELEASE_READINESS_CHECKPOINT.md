# Public Release Readiness Checkpoint

This ledger prevents duplicate review work. Reconsider an entry only when its recorded head, CI result, dependency/advisory state, public claim, blocker state, or steward instruction changes.

## pleiades

- **Default branch:** `main`
- **Last reviewed default head:** `ce40d41d3cb712aef20416b1227edb3d19e988f5`
- **Draft branch:** `hardening/public-release-readiness-v1`
- **Last fully validated draft head:** `5bcec896655d6d6555420073a948d467b229139e`
- **Draft PR:** #34 — deterministic lean source distribution
- **Completed scope:** public claims; bounded release contents; deterministic double build; exact Git-blob manifest; SPDX 2.3 inventory; SHA-256 checksums; build receipt; immutable matching-tag release creation; public tree/history sensitivity scan; removal of misleading GHCR package lane; release provenance attestations; immutable-SHA pinning for release-path Actions; non-persistent release checkout credentials; required artifact-metadata permission for current `actions/attest` behavior; ordinary current-tree redaction of the catalogued Windows profile identity; exact anonymous PR-merge-ref fetching without relying on `actions/checkout` in the read-only validation job.
- **Resolved findings:** non-runnable container-package presentation removed; generic release notes replaced with download-first scope language; release refuses mismatched/non-main-reachable tags and refuses mutation of an existing release; generated artifacts are reproducible and checksum-verifiable; release artifacts receive GitHub/Sigstore provenance attestations; the current `PLEIADES_STATE.md` no longer publishes the catalogued Windows username/profile path; PR validation no longer fails inside the checkout Action before repository checks execute.
- **Open blocker:** issue #42 remains partially open. The ordinary current-tree Windows profile disclosure is redacted, but user-specific paths remain in blobs reachable from the release candidate. They are not credentials or keys. A clean public-history claim still requires an explicitly approved coordinated history rewrite, open-branch rebase plan, and exact post-rewrite rescan.
- **Validation receipts:** ordinary CI run `29775004141` passed at `5bcec896655d6d6555420073a948d467b229139e`. Public-source run `29775004087` passed exact-ref fetch, Python setup, tooling parse, lean invariants, sensitivity capture, deterministic double build, checksum verification, source-boundary receipt verification, and evidence upload; it failed only at the intended final sensitivity gate. Earlier v4.4.0 and v7.0.1 checkout-action attempts failed before repository validation, including with the explicit unsafe-PR override, so the read-only PR validator now performs a minimal anonymous Git fetch of the exact merge ref. The tag-only release workflow retains full-SHA-pinned `actions/checkout` v7.0.1 because it does not consume PR merge refs.
- **Changed conclusion:** the checkout failures followed multiple Action versions and the explicit override, establishing that this repository/ref interaction—not a single release pin—was the operational defect. The safest bounded adaptation is no checkout Action at all in the read-only PR validator, while retaining the current pinned Action in the tag-only publisher. Current-tree redaction is complete; only reachable-history removal remains blocked on explicit rewrite authority.
- **Deferred:** full-SHA pinning for the broader non-release CI workflow after trusted identities for every referenced Action are recorded; coordinated Git history rewrite and affected-branch rebase; release/tag publication.
- **Next action:** skip this repository unless the draft head, CI result, issue #42 authority state, public release claims, or upstream validation dependencies materially change. The next substantive step is a separately authorized history-rewrite plan, not another ordinary draft patch.

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
- PR validation uses an anonymous exact-ref fetch because the third-party checkout Action failed before repository validation across multiple pinned versions; the job remains read-only and receives no repository secrets.
- Checkout credentials are not persisted where subsequent authenticated Git operations are unnecessary.
- Dependency review remains a future candidate where supported package manifests make it useful.
- No external project code was copied.

Trusted upstream identities recorded for this checkpoint:

- tag-release `actions/checkout` `v7.0.1`: `3d3c42e5aac5ba805825da76410c181273ba90b1`
- `actions/setup-python` `v5.6.0`: `a26af69be951a213d495a4c3e4e4022e16d87065`
- `actions/upload-artifact` `v4.6.2`: `ea165f8d65b6e75b540449e92b4886f43607fa02`
- `actions/attest` `v4.1.1`: `a1948c3f048ba23858d222213b7c278aabede763`
