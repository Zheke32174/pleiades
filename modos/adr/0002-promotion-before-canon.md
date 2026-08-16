# ADR-0002: Promotion before canon

- Status: proposed
- Date: 2026-07-17

## Decision

All MODOS integration changes begin on named branches and enter canonical branches only through reviewable pull requests. Experimental and backup branches are preserved with provenance rather than silently merged.

A promotable change must be:

1. machine-measurable;
2. steward-verifiable;
3. ordinary-person noticeable when user-facing;
4. reversible or accompanied by an explicit recovery plan;
5. scoped to declared capabilities;
6. traceable to source evidence and validation receipts.

No draft PR created by this progression is auto-merged.
