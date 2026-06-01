# Owner-Authorized Recovery Helpers

These scripts are **experimental**. They are not installed or activated by default.

They are intended only for operators who own and administer the target system and understand the full effect of each script.

**Always use `--dry-run` first.**

## Scripts

| Script | Purpose |
|--------|---------|
| `install-owner-startup-service.sh` | Installs an owner-authorized startup service so the container starts at OS boot. Supports WSL2 and bare-metal/VPS via systemd. |
| `evidence-preserving-local-cleanup.sh` | Collects and encrypts local evidence bundles, optionally pushes to the private evidence repo, then removes local temporary working files. Destructive cleanup is disabled unless `--cleanup-local --confirm-owned-system` are both provided. |
| `init-owner-recovery-marker.sh` | Writes an owner recovery signal to the configured GitHub repository. Used to coordinate container rebuild after a full wipe. |
| `clear-owner-recovery-marker.sh` | Clears the owner recovery signal. |

## Required Flags for Destructive Operations

`evidence-preserving-local-cleanup.sh` will not delete any local files without:

```bash
--cleanup-local            # enable local file removal
--confirm-owned-system     # confirm this is a system you own/administer
```

Default behavior: collect and encrypt evidence bundle only. No deletions.

## Scope

These tools are for systems the operator owns and explicitly administers. Do not deploy on systems without explicit authorization.
