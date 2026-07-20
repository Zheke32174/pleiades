# Google Drive Artifact Bridge

## Decision

Google Drive is a non-authoritative artifact shuttle and change-notification bridge for Pleiades. It is not a native JuiceFS object backend, a filesystem metadata authority, a POSIX layer, a scheduler, or a promotion authority.

The configured bridge root is supplied at runtime. Personal Drive folder IDs, OAuth credentials, refresh tokens, and channel tokens do not belong in the public repository.

## Relationship to JuiceFS

JuiceFS separates filesystem metadata from file data. Its file data belongs in a supported object-storage backend such as the planned Cloudflare R2 bucket, while its metadata remains in the separately governed metadata engine.

The Drive bridge therefore uses this path:

```text
Pleiades artifact/receipt
  -> content-addressed Drive manifest
  -> resumable Drive transfer
  -> changes.watch wake signal
  -> changes.list reconciliation
  -> exact Drive file metadata
  -> streamed download and local SHA-256 verification
  -> isolated staging object
  -> atomic publish to artifact:// content identity
  -> R2-backed JuiceFS namespace
  -> durable handoff receipt
```

Drive file names and folder paths are presentation metadata. They do not determine artifact identity. The canonical target is derived from the verified SHA-256 digest:

```text
artifact://sha256/<first-two-hex>/<complete-sha256>
```

## Implemented pure boundary

`modos/work-order-controller/drive_bridge.py` contains no HTTP client, OAuth token storage, environment access, subprocess, shell, or JuiceFS invocation.

It implements four pure operations:

### Artifact manifest and upload request

`build_artifact_manifest` binds:

- SHA-256 content identity;
- exact size;
- MIME type;
- bounded display name;
- originating receipt digest;
- configured bridge-folder identity;
- future content-addressed JuiceFS target.

`plan_resumable_upload` produces a credential-free Drive `files.create` resumable-upload descriptor. It requires a caller-supplied pre-generated Drive file ID so an indeterminate create result can be reconciled without creating a second logical file. The descriptor requests only the narrow `drive.file` scope and exact response fields.

Private Drive `appProperties` carry compact bridge metadata:

- `p.schema=artifact-v1`;
- `p.role=juicefs-bridge`;
- `p.sha256=<64 lowercase hex>`;
- `p.size=<decimal bytes>`;
- `p.receipt=<64 lowercase hex>`.

The bridge enforces Drive's count and per-property byte bounds before any later adapter can send the request.

### Change notification reduction

`admit_change_notification` accepts only `changes.watch` `sync` and `change` notifications. It checks:

- expected channel identity;
- channel token, when configured, with constant-time comparison;
- expected resource identity after the watch response is known;
- the canonical Drive v3 changes URI;
- positive message identity;
- supported resource state.

The initial `sync` notification may arrive before the watch response. The reducer can retain that signal when channel identity and token match, but any later `change` requires a prebound resource ID.

A notification contains no authoritative change details. Its output explicitly states:

- notification content is not change content;
- message ordering is not authoritative;
- `changes.list` reconciliation is required;
- the signal carries no action authority.

### Change-feed request planning

`plan_change_feed_poll` emits a bounded `changes.list` request descriptor with an explicit field mask containing only the metadata needed for bridge reconciliation. It does not call Drive or persist a page token.

### File ingest proposal and future handoff

`reduce_file_to_ingest_proposal` accepts only a non-trashed binary file directly parented by the configured bridge folder. It requires exact:

- Drive file and version identity;
- MIME type and bounded name;
- size;
- Drive SHA-256 checksum;
- Pleiades private properties;
- originating receipt digest.

Native Docs, Sheets, and Slides are rejected in version 1. Their exported bytes require a separate contract that binds export MIME type, source revision/version, and exported-content digest.

A valid Drive file still cannot enter JuiceFS directly. The proposal requires a streamed download and local SHA-256 verification. `plan_juicefs_handoff` describes the later isolated staging and atomic content-addressed publication, but performs neither.

## Authority and trust rules

```text
Drive OAuth authentication is not artifact verification.
Drive SHA-256 metadata is not a substitute for hashing downloaded bytes.
A push notification is not a file-change record.
A Drive name or folder path is not canonical artifact identity.
A Drive revision is not a Pleiades promotion transaction.
A successful upload is not a JuiceFS handoff receipt.
Drive is never the sole durable copy.
```

SQL/PDK state remains the metadata, continuity, idempotency, and receipt authority. The future network adapter must use credential separation, durable replay state, bounded exponential backoff, uncertain-effect reconciliation, and receipts before cleanup or retention changes.

## Current live Drive state

A user-owned folder named `Pleiades Bridge` has been created as the intended root. Its ID remains runtime configuration outside the public repository.

No OAuth client, refresh token, watch channel, upload, download, webhook endpoint, JuiceFS mount, R2 write, or live service is created by this branch.
