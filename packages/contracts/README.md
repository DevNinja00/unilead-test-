# Contracts

Shared, versioned contracts consumed by more than one app.

Expected contents (added as they are needed):

- OpenAPI / API contract schemas shared between `apps/api` and `apps/web`.
- Cross-cutting types and domain schemas (e.g. team, project, membership models).
- Validation schemas used by both Python and TypeScript, kept in sync deliberately.

**Rule:** apps depend on `packages/`, never on sibling apps. Changes to a contract
are reviewed like a public API — a breaking change bumps the contract version.