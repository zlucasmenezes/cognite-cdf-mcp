# Contributing

Experimental project — small PRs, CI green, Conventional Commits.

## Workflow

1. Branch from `main`: `feat/…`, `fix/…`, `docs/…`, `chore/…`.
2. Open a pull request (do not push straight to `main` once branch protection is on).
3. Keep the **PR title** as a [Conventional Commit](https://www.conventionalcommits.org/) — with squash merge it becomes the `main` history that drives releases:
   - `feat:` → minor (while on `0.x`, with our Release Please config)
   - `fix:` → patch
   - `feat!:` / `fix!:` or `BREAKING CHANGE:` in the body → minor on `0.x` (`bump-minor-pre-major`), major after `1.0.0`
   - `docs:`, `test:`, `chore:`, `ci:`, `refactor:` → usually no version bump (unless configured otherwise)
4. Wait for CI (ruff + import smoke + pytest).
5. Squash-merge when ready.

### Local checks

```bash
uv sync --group dev
uv run ruff check --fix .
uv run ruff format .
uv run pytest -q
```

Optional: `uv run pre-commit install` so each commit formats the staged files with ruff and rejects a message that is not a Conventional Commit. Push does not run these hooks; CI checks the PR.

## Releases

[Release Please](https://github.com/googleapis/release-please) opens/updates a **Release PR** after conventional commits land on `main`.

- **You control timing:** merge that Release PR only when you want a new tag.
- Merging it bumps `pyproject.toml` / `__version__` / `uv.lock` / `CHANGELOG.md`, creates GitHub Release + tag `vX.Y.Z`.
- Pin installs with `git+https://github.com/zlucasmenezes/cognite-cdf-mcp.git@vX.Y.Z`.

Do not hand-tag from random commits once Release Please is active — let the Release PR own the version.

## Maintainer checklist (GitHub UI — not in this repo)

These cannot be expressed as files in git; configure once in the GitHub repository settings:

1. **Branch protection** on `main`:
   - Require a pull request before merging
   - Require status checks to pass: CI job (e.g. `check`)
   - Do **not** require approving reviews if you are the only maintainer
   - Block force pushes; optionally allow admin bypass for emergencies
2. **Pull request settings**:
   - Default merge method: **Squash and merge**
   - Delete head branches on merge
   - Prefer disabling merge commits (and rebase merge if you want one path only)
3. **Actions / Release Please**:
   - After the first push of `release-please.yml`, confirm the workflow runs on `main`
   - If protection blocks the release bot, allow GitHub Actions (or the release-please app) to open PRs / push release branches as needed
4. **Dependabot**: enable Dependabot alerts/PRs if the org/account has them disabled globally (the `.github/dependabot.yml` in this repo is not enough alone when the feature is off)

Secrets (`CDF_TOKEN`, etc.) must never be added to CI for this project’s default workflows.
