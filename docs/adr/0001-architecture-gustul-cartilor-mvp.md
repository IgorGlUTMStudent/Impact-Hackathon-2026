# ADR-0001: Architecture for the Gustul Cărților P0 MVP

- **Status**: **Accepted by the team for hackathon implementation** on 2026-10-30 (G7 closed following independent architecture review, PR #8). Partner validation of business rules and real-user privacy/consent gates remains pending.
- **Date**: 2026-10-30
- **Deciders**: Vladimir (team lead; final G7 approval), architecture proposal by Arsenii / Claude Code, independently reviewed in PR #8.
- **Details**: [spec](../../specs/001-reading-diary-mvp/spec.md) · [plan](../../specs/001-reading-diary-mvp/plan.md) · [research](../../specs/001-reading-diary-mvp/research.md) · [data model](../../specs/001-reading-diary-mvp/data-model.md) · [routes](../../specs/001-reading-diary-mvp/contracts/routes.md) · [authorization](../../specs/001-reading-diary-mvp/contracts/authorization.md) · [execution plan](../../specs/001-reading-diary-mvp/execution-plan.md)

## Context

Five developers must ship, within the hackathon, one reliable demo: a child logs reading of a physical book, the linked parent sees the stored progress, and a verified club member unlocks a club-only achievement. The product serves children aged roughly 7–15 and must stay useful for adults without children, so authorization, privacy defaults and honest persistence matter more than feature count. One teammate suggested writing everything in Python; this is unconfirmed team input, not a constraint. The club wants maintainable code on GitHub afterwards.

## Decision

1. **Django 5.2 LTS monolith**, server-rendered templates with **HTMX**, packaged as an installable **PWA**, chosen on its merits (built-in auth, CSRF, admin back office, migrations, one process). One process, one database (SQLite on a persistent disk for the demo; Postgres-compatible). The host is chosen only after a host proof passes.
2. **Two presentation modes over one domain**: `templates/child/` and `templates/adult/` render the same view models.
3. **Reader abstraction**: adult accounts and child profiles each have one `Reader`; all shelves, progress, memberships and grants hang off `Reader`. Ownership is one function: own reader or a reader of one's own child. The minimal adult self-reader path is P0 and reuses the same services.
4. **Child mode** is a server-side session state enforced by deny-by-default middleware with an allow-list of routes. Leaving it requires the guardian's **PIN only** (5 failures → 5-minute lock per account); a forgotten PIN is recovered by signing out, which ends the whole session, and signing back in with email + password.
5. **Club membership** is a time-bounded entitlement row per reader, activated by staff in Django admin or by a hashed one-time code redeemed by a guardian; it is evaluated per request and never trusted from the client.
6. **Writes are short, transactional and idempotent.** Client `request_id` is unique per reader; the same ID with other data → 409. On SQLite, transactions are `IMMEDIATE` (one writer at a time, 5 s busy timeout, lock timeout → 503, no auto-retry). `select_for_update` has no effect on SQLite and is not relied on there. Concurrent different IDs apply in commit order. Success is rendered only after commit (HTMX: 401 instead of a followed redirect; "saved" only on `HX-Trigger: saved`); no offline write queue.
7. **Achievements** are granted only by server rules after stored changes, unique per reader; members-only rules check membership at evaluation time.
8. **Single contract style**: HTML forms + HTMX partials; no JSON API in P0.
9. **No AI in P0.** Mascot text is a fixed, translatable script. Future AI sits behind human review (mentor approves generated quizzes).
10. **Three separate DB-backed throttles**: login (custom `ThrottledLoginView`; stock `LoginView` has none), guardian PIN, and membership-code redemption.

## Consequences

- ➕ Built-in auth, CSRF, admin, migrations and constraints cover the riskiest parts with little custom code; easy for AI agents and for handover.
- ➕ Clear module boundaries (apps + template sets) allow five parallel PRs after one foundation PR.
- ➖ Server-rendered UI is less "app-like" than a SPA; mitigated by HTMX partials and PWA install.
- ➖ SQLite allows one writer at a time and gives no row locks; near-simultaneous writes queue for up to 5 s or fail visibly with 503. Acceptable for a demo with a few devices; no capacity is claimed; switch to Postgres if rehearsal shows lock errors.
- ➖ A free-tier host with one worker and a CPU quota gives no performance guarantee; latency is measured, not promised.
- ➖ The foundation PR (all models) is a bottleneck; mitigated by keeping it small and letting UI and service work start against documented contracts.

## Alternatives considered

FastAPI + SQLAlchemy + Jinja/HTMX (more custom auth/admin code); Next.js + Supabase (credible; two vendors, back office to build, authorization in untested RLS policies); Flet/Reflex/NiceGUI (weak PWA/accessibility, tight UI–state coupling). See [research.md §2](../../specs/001-reading-diary-mvp/research.md#2-options-compared).

## Open decision gates

G1 KPI · G2 child accounts/consent (Law 195/2024, unverified) · G3 membership verification · G4 reward semantics · G5 social/leaderboard for minors · G6 delivery/hosting/assets remain open. **G7 stack sign-off is CLOSED / ACCEPTED 2026-10-30**. See [spec](../../specs/001-reading-diary-mvp/spec.md#decision-gates-blocking-items-need-answers-before-freezing).
