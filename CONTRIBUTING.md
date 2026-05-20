# Contributing to Orbit-Shield

Thanks for taking the time to contribute. This document covers the workflow for proposing changes and the standards we hold contributions to.

By participating you agree to abide by the [Code of Conduct](CODE_OF_CONDUCT.md).

---

## Ways to contribute

- **Bugs** — open an issue with a minimal reproduction.
- **Features** — open an issue first so we can align on scope before you build.
- **Documentation** — corrections and clarifications are always welcome.
- **Security issues** — see [`SECURITY.md`](SECURITY.md). Do not open public issues for vulnerabilities.

---

## Development setup

The fastest path from a fresh clone to a working dev environment is the Docker quickstart in the [README](README.md#quickstart-docker). If you prefer running services directly, follow [Local development (no Docker)](README.md#local-development-no-docker).

Minimum versions:

- Python **3.12** (project pins `>=3.12,<3.14`)
- Node **20**
- Docker Desktop (or compatible runtime) for Postgres + Redis

Recommended: [`uv`](https://docs.astral.sh/uv/) for fast Python installs.

---

## Branching and PR flow

1. Fork the repo and create a topic branch off `main`:
   ```bash
   git checkout -b feat/your-feature-name
   ```
2. Make focused commits — one logical change per commit where possible.
3. Push the branch and open a pull request against `main`.
4. Ensure CI is green. PRs are blocked from merging until checks pass.
5. A maintainer will review. Address feedback by pushing additional commits — we squash on merge.

**Branch naming convention:**

| Prefix     | Use for                              |
| ---------- | ------------------------------------ |
| `feat/`    | new user-facing functionality        |
| `fix/`     | bug fixes                            |
| `chore/`   | tooling, deps, CI                    |
| `docs/`    | documentation only                   |
| `refactor/`| no behavior change                   |
| `test/`    | tests only                           |

---

## Commit messages

We use **Conventional Commits**:

```
<type>(<scope>): <short summary>

[optional body explaining the why]
```

Common types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `perf`, `ci`, `build`.

Examples from the repo history:

```
fix(db): handle Neon idle-connection drops with pre-ping + recycle
feat(ui): full responsive cascade (mobile→ultrawide)
ci: add test workflow
```

Keep the subject line ≤ 72 characters. Use the body for the *why* — the diff already shows the *what*.

---

## Coding standards

### Python (backend)

- **Formatter:** Black (line length 88).
- **Linter:** Ruff.
- **Type checker:** mypy (`strict = true`).
- Type hints everywhere; Google-style docstrings on public functions.
- Prefer explicit over clever — this is safety-adjacent domain code.
- All orbital computations operate in **TEME frame** internally and convert to **GCRS** for output.

Run before pushing:

```bash
cd backend
black src tests
ruff check src tests
mypy src
pytest
```

### TypeScript (frontend)

- TypeScript **strict mode**; no `any` without a justification comment.
- Functional components with hooks. State via Zustand.
- ESLint via `npm run lint`.
- Production build must succeed: `npm run build`.

```bash
cd frontend
npx tsc --noEmit
npm run lint
npm run build
```

---

## Tests

Every behavior change needs a test. Bug fixes get a regression test that fails on `main` and passes on your branch.

```bash
# Backend
cd backend && pytest

# A single test
pytest tests/test_screening.py -k test_kdtree_finds_close_pair

# Frontend
cd frontend && npx tsc --noEmit && npm run build
```

CI runs the same commands on every push and PR. Both backend and frontend must be green.

---

## Database migrations

If you change `backend/src/db/models.py`, add an Alembic migration:

```bash
cd backend
alembic revision --autogenerate -m "describe your change"
# Review the generated file under alembic/versions/ before committing
alembic upgrade head     # applies it locally
```

Never edit migrations that have already been merged to `main` — add a new one.

---

## Domain conventions

Orbit-Shield touches safety-relevant computations. A few non-negotiables:

- ML models **enhance** classical Pc — they never replace it. Always retain and surface the classical value.
- All time series are in **UTC**.
- Distances in **km**, velocities in **km/s**, angles in **degrees** for API surfaces; internal compute may use radians/SI but must convert at boundaries.
- Maneuver decision threshold: **Pc ≈ 1e-4**. Don't change this constant without a thread on the PR justifying it.

---

## Code review expectations

- A maintainer will respond within ~3 business days.
- Reviews focus on correctness, testability, and consistency with surrounding code.
- We squash on merge; your individual commit messages will be combined into the PR title + body.

---

## Reporting bugs

When opening an issue:

1. **What you did** — minimal reproduction or commands you ran.
2. **What you expected.**
3. **What happened** — full error message + stack trace.
4. **Environment** — OS, Python/Node version, deploy target (local / Docker / Fly.io).

---

## Questions

For general usage questions, open a GitHub Discussion (preferred) or a regular issue. For security issues, follow [`SECURITY.md`](SECURITY.md).
