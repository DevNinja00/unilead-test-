# Documentation

Documentation is reviewable like code. This index covers what lives here and
where to put new docs.

## Layout

| Path      | Purpose                                                                 |
|-----------|-------------------------------------------------------------------------|
| `adr/`    | Architectural Decision Records (one file per decision, numbered `NNNN-`). |
| `apps/`   | Per-app docs may live alongside code; this root index links the big ones. |

## Writing an ADR

Use the lightweight template below. Number decisions sequentially and never rewrite
history — append new ADRs and supersede old ones.

```md
# NNNN: <Title>

Status: Proposed | Accepted | Superseded by NNNN

## Context
## Decision
## Consequences
```

## Onboarding

See the [CONTRIBUTING.md](../CONTRIBUTING.md) workflow and the Quickstart section of
the root [README](../README.md). Environment setup, local development, and test
instructions live in each app's README as apps are scaffolded.