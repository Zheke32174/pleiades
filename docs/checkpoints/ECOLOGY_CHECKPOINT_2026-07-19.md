# Pleiades ecology checkpoint — 2026-07-19

This ledger records the current stacked hardening wave before further implementation. It is a coordination artifact, not a release, merge, deployment, promotion, or live-system receipt.

## Green stacked drafts

| Repository / PR | Head | Proven boundary |
|---|---|---|
| `pleiades#20` | `40c2c547bcf112c96917458868d2ee75473a663b` | Shared observation-ingress batches, signed receipts, canonical digests, and delivery-stream continuity. Contract validation and full CI passed. |
| `pleiades-container#9` | `51be9c04c82ce763bf42f0a8d464fc3b8f109fa8` | Transactional host binding, rollback fixtures, symlink refusal, and ambient nspawn settings disabled. CI passed. |
| `pleiades-windows#6` | `4e288f7b8d1a9d6e51fc5619ed6ce3cfb4ce0af7` | Typed WSL lifecycle argv, canonical machine/unit identity, installed-root binding, and fail-closed recovery classification. Windows CI passed. |
| `pleiades-termux#5` | `278aa2e7214be36252d0b6da8cc0ae94684eacff` | Stable delivery-stream identity, contiguous delivery positions, crash recovery, legacy adoption, and truthful zero acknowledgement. CI passed. |
| `pleiades-factory-stack#6` | `0f165883870bc3575d9b0d5aa6b8add21cc40f6f` | Transactional top-level source locks and explicit non-reproducible dirty-tree identity. CI passed. |

## Open containment stack

`undergrowth#27` at `1facd04da25516c50e0f90c9b1ad5ed17781c647` makes the ordinary inheritance path inert by default, gates the broad historical estate, disables third-party setup by default, and receipt-gates sensitive repository access.

Its GitHub coherence job failed before producing any steps, logs, or artifacts. That result is not treated as a code-validation receipt.

## Understory runner checkpoint

The review-first admission and migration work remains on `understory#32`. The historical runtime still requires containment before disposable execution validation:

- every path must derive from `UNDERSTORY_OBJECTIVE_ROOT`;
- a missing tier must enter review rather than automatic execution;
- approval must bind the exact executable objective;
- corrupt records must be quarantined rather than collapsed to empty state;
- state transitions must be private and atomic;
- only explicitly owned child processes may be terminated;
- restart must not kill or duplicate an unproven historical child.

A local replacement design and adversarial fixture set were exercised during this checkpoint, but no runner implementation was committed because the repository write gate rejected the operational patch. The attempted branch was reset to the exact `understory#32` head, leaving no partial file change.

## Ordered next work

1. immutable and content-addressed Factory evidence and decision generations;
2. durable receiver-side observation admission behind `pleiades#19` and `pleiades#16`;
3. Understory runner containment through a reviewable, independently testable split rather than one large historical-file replacement;
4. machine-readable inheritance profiles and exact repository provenance;
5. Windows delivery-stream continuity separate from Security `RecordId`;
6. annotated-tag and recursive dependency identities for Factory Stack.

## Discipline

Child stacks must retain their declared bases until parent contracts are reviewed. No automatic merge, release, tag, live deployment, service start, evidence deletion, compaction, or ontology promotion follows from this checkpoint.
