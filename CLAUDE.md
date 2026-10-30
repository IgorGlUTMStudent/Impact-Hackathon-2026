# Claude Code Guidelines — Impact Hackathon 2026

Claude Code should follow the shared project guidelines and team constitution:

1. **Shared Agent Guidelines**: [AGENTS.md](AGENTS.md) — Comprehensive rules on repository reconnaissance, boundary respect, Spec Kit baseline hygiene, verifiability, and Pull Request workflows.
2. **Team Constitution**: [.specify/memory/constitution.md](.specify/memory/constitution.md) — Fundamental operational principles (Demo-first MVP, time-boxing, shared contracts, parallel work, security).

### Essential Directives:
- **Case #1 Gustul Cărților and G7 stack are approved (2026-10-30):** Django 5.2 LTS + HTMX 2.x + installable PWA (Python 3.12). Follow `docs/adr/0001-architecture-gustul-cartilor-mvp.md` and the reviewed `specs/001-reading-diary-mvp/` contracts. Foundation implementation is permitted within a task/PR; partner validation of G1–G6 and security tests remain outstanding.
- The shared Git baseline must stay agent-neutral (`none`). If you use local Spec Kit skills via `specify integration switch claude`, switch back to `specify integration switch none` before staging or committing changes.
- Never report simulated test passes; execute real commands and report actual outputs.
- Push task branches directly to GitHub for review and link to the relevant issue. Do not merge into `main`.
