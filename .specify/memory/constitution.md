# Impact Hackathon 2026 Team Constitution

## Core Principles

### I. Demo-First & End-to-End MVP
The primary objective of the hackathon is delivering a working, end-to-end user journey ready for live demonstration. Features that cannot be reached or experienced in the demo have zero score value. Priority is always given to the vertical slice over isolated horizontal layers.

### II. Time-Boxing & Critical-Path Focus
Every task must be evaluated against Impact, Effort, and Risk before starting work. Critical-path blockers take absolute priority. Avoid premature optimization, exhaustive refactoring, or polishing non-critical elements before the core demo flow is demonstrably working.

### III. Shared Contracts & Explicit Decision Gates
Shared interfaces, API specifications, database schemas, and shared data models must have a single source of truth in the repository. Any change to a shared contract represents an explicit decision gate: it must be agreed upon by affected team members before code implementation begins.

### IV. Parallel Work & Conflict Avoidance
Team members work in isolated feature branches with small, focused Pull Requests. Clear file ownership and module boundaries prevent overlapping edits. Independent modules proceed concurrently; shared core code is integrated incrementally in small batches.

### V. Verifiability & Honest Smoke Checks
Code must be verifiable. Every Pull Request must report concrete, executable checks (smoke tests, manual reproduction steps, or automated tests for critical paths). Never report fictional or unverified "PASS" results; document real command outputs and known edge-case limitations.

### VI. Fact-Based Reasoning & Handling Uncertainty
Hackathon requirements, jury criteria, domain constraints, and technical stack details are accepted as facts only once officially announced by organizers. Assumptions must be explicitly flagged as `[ASSUMPTION]`. Architectural decisions and technology selections remain deferred until the challenge specifications are published.

### VII. Pragmatic Spec-Driven Development (SDD)
Spec Kit is an alignment and acceleration tool, not a bureaucratic ritual. Full specification cycles (`specify -> clarify -> plan -> tasks -> implement`) are reserved for non-trivial features and complex modules. Urgent hotfixes and trivial adjustments within tight timeboxes do not require heavy documentation ceremonies.

### VIII. Security & Compliance
Never commit secrets, API keys, credentials, or personal identifiable data (PII). Respect all hackathon rules, environment boundaries, and organizer terms. Sanctioned paths and documented tooling must be used at all times.

## Governance & Amendment Policy

1. **Supremacy**: This Constitution defines the team's operational and development baseline for Impact Hackathon 2026.
2. **Amendments**: Amendments require consensus among active team members. Any modification must update the version number and last-amended date below, along with a concise justification in the accompanying Pull Request.
3. **Challenge Ingestion**: Upon official release of hackathon tracks and constraints, the team will review this constitution to adopt any track-specific technical requirements without violating core principles.

**Version**: 1.0.0 | **Ratified**: 2026-10-30 | **Last Amended**: 2026-10-30
