# Pleiades Test Ledger

This file records public-safe test summaries for Pleiades. It is not an evidence archive and must not contain private logs, credentials, hostnames, IP addresses, screenshots, personal identifiers, or incident-specific data.

Use this ledger to show that the project is being exercised on owned systems without exposing sensitive details.

## Rules

- Record only sanitized outcomes.
- Do not paste raw logs.
- Do not include private host metadata.
- Do not include tokens, keys, paths to private vaults, evidence bundles, or third-party target details.
- Keep real forensic material in the private evidence archive only.
- Prefer pass/fail/skip counts and short notes over verbose output.

## Entry template

```text
## YYYY-MM-DD — Environment label

Environment:
- Host class: local Linux / WSL2 / VPS / Termux / other
- Ownership: owned or explicitly administered by operator
- Scope: local defensive lab / container regression / Termux adaptation / factory tooling

Commands:
- command 1
- command 2

Results:
- PASS: 0
- FAIL: 0
- SKIP: 0
- Overall: PASS / FAIL / PARTIAL

Notes:
- Public-safe summary only.
- No private logs attached.
```

## Current known validation paths

These are the intended validation paths described by the repository and should be recorded here when run:

```bash
bash -n root.x86_64/scripts/*.sh
bash root.x86_64/scripts/pleiades-regression.sh --dry-run
bash root.x86_64/scripts/pleiades-regression.sh
```

For Termux-adapted testing:

```bash
source env/pleiades-env.sh
bash env/bootstrap-termux.sh
pleiades info
```

## Test entries

Add newest entries at the top.

