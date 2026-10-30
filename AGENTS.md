# Agent Guidelines — Impact Hackathon 2026

Universal guidance for AI coding agents (**Antigravity**, **Codex**, and any CLI-driven agent operating in this repository).

## 1. Primary Directives & Constitution
- Strictly adhere to the team principles defined in [`.specify/memory/constitution.md`](.specify/memory/constitution.md).
- Prioritize demo-first end-to-end value over premature optimization or non-essential refactoring.
- **Gustul Cărților (case #1) selected; G7 stack approved on 2026-10-30**: Django 5.2 LTS + HTMX 2.x + installable PWA, Python 3.12. Read `docs/adr/0001-architecture-gustul-cartilor-mvp.md` and `specs/001-reading-diary-mvp/` before implementation. This approves a technical direction, not every proposed partner feature: G1–G6 remain pending. Do not implement deferred features or change shared schema/contracts without a review gate.

## 2. Working with Code & Files
- **Reconnaissance first**: Always inspect actual repository state (`git status --short`, file contents, existing contracts) before modifying code. Never assume files or dependencies exist.
- **Respect module boundaries**: Work only on files within your assigned task scope. Never edit files owned by teammates or shared infrastructure without explicit coordination.
- **Shared contracts**: Schema, API, or contract alterations are decision gates. Discuss and agree before modifying shared interfaces.

## 3. Spec Kit Baseline Hygiene
- The shared repository baseline in `main` is agent-neutral (`installed_integrations = ["none"]`, `default_integration = "none"`).
- If you or your user locally switch integrations (`specify integration switch agy|codex|claude`), **revert to `none` before committing**:
  ```bash
  specify integration switch none
  git checkout -- .specify/integrations/none.manifest.json  # if timestamp churn occurred
  specify integration status
  ```
- Never commit agent-specific folders (`.agents/`, `.claude/`, etc.) or local environment overrides into Git.

## 4. Testing, Verification & Pull Requests
- **No fictional results**: Report only real, executed commands and actual outputs. Never claim a test passed if it was not run.
- **Document limitations**: Every PR must state:
  1. What was implemented and which issue it addresses (`Refs #<id>` / `Closes #<id>`).
  2. Exact verification commands executed and their output.
  3. Known limitations, edge cases, and follow-up work.
- **Push immediately**: Push your branch to GitHub immediately upon completing the task so teammates and independent reviewers (e.g. ChatGPT reviewer) can inspect the code.
- **No unauthorized merge**: Never merge your own PR into `main` without review.

## 5. Project Commands (Django foundation, M0)
- Install: `uv sync --frozen` (Python 3.12 via `uv`; copy `.env.example` to `.env` for local values)
- Database: `uv run python manage.py migrate` then `uv run python manage.py seed_demo` (synthetic data, idempotent)
- Test: `uv run pytest`; schema drift: `uv run python manage.py makemigrations --check --dry-run`
- Run: `uv run python manage.py runserver`; health check at `/healthz/`; DEBUG-only template preview at `/_preview/adult/…` or `/_preview/child/…`
- Shared schema (`apps/*/models.py`, migrations) and `config/` belong to the foundation owner until M1; propose changes in the PR thread (see `specs/001-reading-diary-mvp/tasks.md`).
