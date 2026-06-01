# Contributing

Contributions should preserve the defensive, owner-authorized scope of the project.

## Before Submitting Changes

1. **Do not add offensive capability** — no stealthier persistence, evasion, or unauthorized access mechanisms.
2. **Do not add unauthorized-deployment patterns** — all installation should be explicit and owner-authorized.
3. **Do not include secrets** — no credentials, logs, evidence, private host metadata, or `.env` files.
4. **Use clear defensive language** — avoid terms like "selfdestruct", "dead drop", "payload", "wipe traces", "persistence" without "owner-authorized" context.
5. **Default to safe behavior** — scripts should default to `--dry-run` or read-only modes.
6. **Gate destructive operations** — require explicit flags (`--confirm-owned-system`, `--cleanup-local`) for anything irreversible.
7. **Keep experimental work quarantined** — recovery/cleanup/startup helpers go under `experimental/owner-authorized-recovery/`.
8. **Update documentation** — update README and inline comments when behavior changes.
9. **Verify syntax** — run `bash -n` on all modified shell scripts before submitting.

## Pull Request Checklist

- [ ] `bash -n root.x86_64/scripts/*.sh` passes
- [ ] No prohibited language in docs (see CI wording guard)
- [ ] No credentials or private metadata committed
- [ ] `--dry-run` behavior preserved or added for risky scripts
- [ ] DISCLAIMER.md scope is not violated

## Scope

Pleiades is a defensive container lab. Contributions that expand scope to offensive, stealth, or unauthorized-deployment capability will not be merged.
