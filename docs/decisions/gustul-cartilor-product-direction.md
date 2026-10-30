# Gustul Cărților — product direction and architecture decision gates

**Date:** 2026-10-30  
**Status:** team-approved product *direction*; partner requirements, detailed permissions, implementation contracts and stack are still pending.  
**Evidence:** [meeting discovery brief](../discovery/gustul-cartilor-meeting-2026-10-30.md) and [Issue #4](https://github.com/Slave-of-Skynet/Impact-Hackathon-2026/issues/4).

## 1. Team decisions — design constraints for the next Spec Kit specification

1. **One product for general readers and verified club members.** A non-member must have a useful reading experience, not just a marketing screen. Club membership unlocks additional benefits; exact entitlements are not yet approved by the club.
2. **Two distinct interfaces for the same shared product:**
   - **Child experience:** minimal navigation, large readable actions, friendly mascot, visible reading progress, playful feedback, age-appropriate challenges and rewards.
   - **Parent/adult experience:** fuller book discovery, reading history and statistics, child progress visibility, profile/guardian settings, and club information.
   - **Adult readers without children** must remain supported by the adult experience.
3. **Shared reading data:** progress entered in a child experience can be viewed in an authorized linked guardian's experience. Do not duplicate underlying reading records per interface.
4. **Role and membership are separate concepts:** a child's/parent's permissions and a person's club-membership entitlements must not be represented as one mutually exclusive user type.
5. **Core product themes:** reading journal/library, progress/statistics, book discovery/recommendations, club engagement and differentiated member-only gamification.
6. **Single compelling demo journey first:** show a book selected, reading progress updated, corresponding parent statistics updated and a club-only achievement unlocked.

These are **team product decisions**, not proof that the club has approved every implementation detail or business rule.

## 2. Partner discussion — candidate features, NOT binding requirements

- Book recommendations (genre/history/preferences), book catalog, reading status/progress bar.
- Individual and total reading ranking/leaderboard; public visibility was discussed, but the final minor privacy policy was not agreed.
- Duolingo-inspired levels, achievements and club rewards; partner mentioned an existing reward mechanism.
- Membership code and activity reminders as possible club benefits.
- Parent-child usage and potentially reading together, not yet specified precisely.
- Short-form book discussion/reviews ("like Twitter"); only after safety/moderation decisions.
- Full online reading **tentative**; partner says it does not provide copies, and distribution rights are unknown.
- Mentors work with groups rather than being assigned individually to every child; do not assume individual mentor chats.

## 3. Proposed hackathon scope (recommendation, not approved)

**P0 vertical slice:** mobile-first catalog/diary; child adds a book and logs progress; parent views updated progress/stats; switch or verification of club membership unlocks one achievement/activity; private child profile by default. Use synthetic demo accounts and rights-cleared book metadata.

**P1 after P0 works:** basic genre recommendations, moderated short reviews, safe leaderboard, more club activities and parent-guided reading.

**Defer:** full ebook repository/reader, production subscription payments, native iOS/Android release, AI-dependent core flows, unrestricted child social network, Roblox rewards and personalized 1:1 mentor systems.

**Technical preference only:** one responsive web/PWA with role-specific screens and shared services rather than two independently maintained applications. Final architecture/stack must be approved in Spec Kit planning.

## 4. Architecture decision gates — require explicit answers

| Gate | Essential question | Safe temporary assumption for prototyping |
|---|---|---|
| Product success | Is the priority club acquisition, reader retention, scalable remote participation or mentor workload reduction? What one KPI matters? | Demo a complete reading-to-parent-feedback journey; don't assert commercial KPI |
| Child identities | Age range, guardian consent and linking method? Can children sign in independently? | Demo with synthetic parent-linked child, child private by default |
| Access and membership | Who verifies club membership, how is it revoked, and which benefits are gated? | Server-checked demo entitlement, no real billing or self-issued permanent codes |
| Progress/rewards | Is progress measured in pages, chapters, time or completed books? How is a club reward verified? | Pages or completion as demo metric; digital sample achievement only |
| Social/leaderboard | Can minors publish reviews or enter rankings, and what moderation/visibility is approved? | Omit open posting/identifiable public leaderboard from P0 |
| Delivery/data | Is installable PWA acceptable, which languages and books/assets are authorized, and where will it be hosted? | Responsive web demo using sample/authorized content; no full copyrighted texts |

**Decision rule:** do not freeze shared API, authentication, database schema, or public child-data exposure until gates 2–5 are resolved. Reversible UI mockups may proceed in parallel.

## 5. Execution and verification

Use the existing [team constitution](../../.specify/memory/constitution.md), Spec Kit and team agent guidance. Following partner clarification, produce `spec.md` with testable acceptance criteria, then a minimal plan with agreed shared contracts and separate workstreams for Vladimir (Antigravity), Alisa (Codex), Arsenii (Claude Code), Igor (Codex/Antigravity), and Denis (Antigravity). Each implementation agent pushes a separate branch and PR for independent review; changes are never described as tested without real evidence.
