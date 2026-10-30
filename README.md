# Impact Hackathon 2026

Pre-challenge repository setup and collaborative workflow configuration using [GitHub Spec Kit](https://github.com/github/spec-kit).

> [!NOTE]
> The hackathon track, product requirements, technology stack, and architecture are currently **TBD** (awaiting official challenge announcement). This repository contains only team collaboration rules, agent guidelines, and Spec Kit scaffolding.

- **Issue tracking**: [Issue #1 — Pre-challenge setup](https://github.com/Slave-of-Skynet/Impact-Hackathon-2026/issues/1)
- **Architecture proposal (under review, Issue #7)**: [`specs/001-reading-diary-mvp/`](specs/001-reading-diary-mvp/spec.md) · [ADR-0001](docs/adr/0001-architecture-gustul-cartilor-mvp.md)
- **Team Constitution**: [`.specify/memory/constitution.md`](.specify/memory/constitution.md)
- **Agent Instructions**: [`AGENTS.md`](AGENTS.md) (universal / Antigravity / Codex) & [`CLAUDE.md`](CLAUDE.md) (Claude Code)

---

## 1. Team & AI Tooling

| Team Member | AI Tool | Primary Role / Responsibility |
|---|---|---|
| **Владимир** | Antigravity | *TBD (post-announcement)* |
| **Алиса** | Codex | *TBD (post-announcement)* |
| **Арсений** | Claude Code | *TBD (post-announcement)* |
| **Игорь** | Codex & Antigravity | *TBD (post-announcement)* |
| **Денис** | Antigravity | *TBD (post-announcement)* |

*Note: Roles and component ownership will be assigned after challenge tracks are announced. Do not infer architectural specialization solely from the AI tool.*

---

## 2. Getting Started & Local Setup

### Clone Repository
```bash
git clone https://github.com/Slave-of-Skynet/Impact-Hackathon-2026.git
cd Impact-Hackathon-2026
```

### Spec Kit Agent Integrations

The committed baseline in `main` is strictly **agent-neutral** (`installed_integrations = ["none"]`, `default_integration = "none"`). Each team member switches to their preferred agent integration locally.

#### Local switching by tool:
- **Владимир / Денис (Antigravity)**:
  ```bash
  specify integration switch agy
  ```
- **Алиса (Codex)**:
  ```bash
  specify integration switch codex
  ```
- **Арсений (Claude Code)**:
  ```bash
  specify integration switch claude
  ```

#### Special Case for Игорь (Codex + Antigravity):
Because Antigravity is not multi-install safe (`Multi-install Safe: no`), simultaneous usage of Codex and Antigravity in the same directory will cause conflicting file modifications.
1. **Simultaneous work**: Use separate Git worktrees for each agent:
   ```bash
   # In root repo:
   git worktree add ../impact-codex -b feature/codex-subtask
   git worktree add ../impact-agy -b feature/agy-subtask

   # Inside ../impact-codex:
   specify integration switch codex

   # Inside ../impact-agy:
   specify integration switch agy
   ```
2. **Sequential work**: If using a single working tree, switch to the second agent only after the first agent has finished and is no longer touching workspace files.

---

## 3. Reverting to Neutral Baseline Before Committing

**Never commit agent-specific folders (`.agents/`, `.claude/`) or modified integration manifests to GitHub.**

Before staging and committing your changes, always revert your local checkout to `none`:

```bash
# 1. Switch back to neutral baseline
specify integration switch none

# 2. Reset none.manifest.json if its timestamp was touched
git checkout -- .specify/integrations/none.manifest.json

# 3. Verify clean integration status (must report default: none, installed: none)
specify integration status

# 4. Verify no agent artifacts remain staged or untracked
git status --short
```

---

## 4. Post-Announcement Development Lifecycle (SDD)

Once the hackathon challenge is selected and approved, features follow the pragmatic Spec-Driven Development cycle:

1. **`specify`**: Define user stories, requirements, and acceptance criteria in `specs/`. Focus on end-to-end demo value.
2. **`clarify`**: Resolve ambiguities, identify assumptions (`[ASSUMPTION]`), and align on boundaries.
3. **`plan`**: Design technical contracts (API, schemas, models). **Shared contracts require explicit team alignment before implementation.**
4. **`tasks`**: Break down work into small, independent tasks suitable for parallel execution across branches.
5. **`implement`**: Implement vertical slices, conduct verifiable smoke tests, and submit small Pull Requests.

*For trivial bug fixes or rapid adjustments during the hackathon crunch, full ceremony is omitted in favor of time-boxed direct delivery.*

---

## 5. Verified Repository Commands

These commands are verified in this repository:

| Command | Purpose | Expected Result |
|---|---|---|
| `specify version` | Check Spec Kit version | Reports `CLI Version 1.2.5` |
| `specify check` | Verify available coding agent CLIs | Lists installed agent CLIs |
| `specify integration status` | Check integration baseline | Reports `Default: none`, `Installed: none`, `Status: OK` |
| `git status --short` | Verify clean working tree | No unexpected modified or untracked files |
| `git diff --check` | Check for syntax/whitespace defects | Clean output (no errors) |

---

## 6. Git & Collaboration Workflow

1. **Branching**: Branch off `origin/main` using descriptive prefixes:
   - `feat/<task-name>`
   - `fix/<issue-name>`
   - `chore/<task-name>`
2. **Pull Requests**:
   - Keep PRs small and targeted.
   - Reference the relevant GitHub issue (`Refs #<id>` or `Closes #<id>`).
   - Include exact verification commands executed and real outputs.
   - Note any known limitations.
3. **Review & Merge**:
   - Push immediately to GitHub upon completion.
   - Do not merge without review (e.g. independent review via ChatGPT or teammate sign-off).
