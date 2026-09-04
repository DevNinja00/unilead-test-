# Contributing to Unilead

Thanks for contributing to Unilead. This guide covers branching, commits, and pull
request review standards. Following it keeps the repository history readable and
reviews fast.

## Table of Contents

1. [Development flow](#development-flow)
2. [Git branching](#git-branching)
3. [Commit messages (Conventional Commits)](#commit-messages-conventional-commits)
4. [Opening a pull request](#opening-a-pull-request)
5. [Pull request review](#pull-request-review)
6. [Issue reporting](#issue-reporting)

## Development Flow

- **`main`** is the integration branch and must always be deployable.
- All work happens on short-lived branches merged via Pull Request.
- Document anything architectural in `docs/adr/` as an ADR.

## Git Branching

Branches are named by intent so history is self-explanatory:

| Prefix    | Purpose                                    | Example                  |
|-----------|--------------------------------------------|--------------------------|
| `feature/`| New user-facing or internal capability     | `feature/team-roster`    |
| `bugfix/` | Defect fix (non-urgent)                    | `bugfix/login-redirect`  |
| `hotfix/` | Critical production fix                    | `hotfix/auth-timeout`    |
| `chore/`  | Tooling, refactor, dependencies            | `chore/upgrade-ci`       |
| `docs/`   | Documentation-only changes                 | `docs/adr-coaching-feed` |

Conventions:

- Branch from the latest `main`: `git switch main && git pull && git switch -c feature/<name>`.
- Keep branches small and focused; one logical change per branch.
- Rebase or merge `main` into your branch before opening a PR, and keep it updated
  if the PR stays open for a while.
- Delete the branch after the PR is merged.

## Commit Messages (Conventional Commits)

We follow [Conventional Commits](https://www.conventionalcommits.org/). Format:

```
<type>(<optional scope>): <summary>

<optional body explaining the why>
```

Common types:

- `feat` — a new feature
- `fix` — a bug fix
- `docs` — documentation only
- `style` — formatting, no logic change
- `refactor` — code change that is neither a fix nor a feature
- `test` — adding or updating tests
- `chore` — maintenance, tooling, dependencies
- `ci` — CI config and workflows
- `build` — build system or packaging

Rules:

- Use the imperative mood, lowercase summary, no trailing period: `fix: resolve login redirect after session expiry`.
- Scope is optional but encouraged: `feat(api): add team invites endpoint`.
- One logical change per commit — split unrelated changes.
- Breaking changes: add `!` after type/scope: `feat(api)!: rename team endpoints`.

## Opening a Pull Request

- Always provide a PR description using the [pull request template](.github/pull_request_template.md).
- Keep PRs small and reviewable (a single focused task is ideal).
- Ensure the PR checklist is complete before requesting review.
- Link the related issue (`Closes #123`) so it auto-closes on merge.

## Pull Request Review

- Every PR requires **at least one approving review** from another contributor
  before it can be merged.
- CI must be green (tests pass, lint/type checks pass) before merge.
- Authors should not merge their own PRs without a second review.
- Reviewers: be specific and actionable; flag blocking issues vs. nits (prefix nits
  with `nit:`).
- Authors: respond to every comment — fix, or explain why not. Resolve threads
  only after addressing them.

## Issue Reporting

- Use the [bug report](.github/ISSUE_TEMPLATE/bug_report.md) and
  [feature request](.github/ISSUE_TEMPLATE/feature_request.md) templates.
- Include reproduction steps, expected vs. actual behavior, and environment info.

Thank you for helping build Unilead.