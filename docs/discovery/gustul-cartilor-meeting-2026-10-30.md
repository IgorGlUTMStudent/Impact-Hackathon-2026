# Gustul Cărților — meeting discovery brief (30 October 2026)

> **Status:** evidence from a partner meeting, **NOT** an approved product specification. Source: team-supplied 24m49s audio, Romanian/Russian; automatically transcribed. Timecodes are approximate, and speaker labels may be inaccurate. Original audio/transcript are deliberately not published. Track partner approval in [Issue #4](https://github.com/Slave-of-Skynet/Impact-Hackathon-2026/issues/4).

## 1. Existing operation — reported by participants

| Timestamp | Reported fact | Confidence / caveat |
|---|---|---|
| 00:25–01:03 | Club already sells subscriptions. The ASR transcript mentions monthly and annual terms. | **Check**: public site differs |
| 05:00–05:18 | A general book-tracking app for everyone (including adults), not merely an exclusive club app, is discussed. | Direction agreed in conversation; precise scope TBD |
| 06:54–07:13 | Children mostly use physical books; the club does not supply book copies. Families borrow or buy them. | High |
| 07:19–07:58 | Invited mentor works across groups over ~3 months, not one-to-one. Around 70+ children, approximately 20+ per group, two activities per month: club-led and mentor-led. | Reported, approximate counts |
| 08:20–08:43 | A reading diary is named as a central purpose. Club already has around 70 participating families. | High |
| 09:20–09:27 | Club says it already has a reward/bonus mechanism. | Details unknown |

## 2. Features discussed — NOT final requirements

| Timestamp | Proposal / discussion | Status |
|---|---|---|
| 02:50–04:10 | Free trial/demo period (14 days or one month suggested), guardian consent before payments. | Brainstorming; do not implement billing on this basis |
| 05:18–06:01 | Membership code to unlock club-specific functionality and event reminders. | Option only; no authorization mechanism selected |
| 06:02–06:22 | Availability on phones (iOS/Android) and computers, with a link from the existing website. | Device objective; implementation format not chosen |
| 08:49–10:32 | Age restrictions, progress bar, milestone levels by completed books, bonuses, overall/personal reading ranking, profile visibility. | Candidate features with privacy decision gate |
| 11:54–12:50 | Catalog and recommendations based on previous reads, genres or selected preferences. | Candidate; no AI requirement established |
| 14:37–15:04 | Duolingo-style achievements/levels used as a UX reference. | Inspiration, not copying |
| 15:37–16:40 | Functional demonstration rather than a fully finished native mobile app. Performance concerns discussed, not measured. | Hackathon framing |
| 17:27–18:30 | Later clarification: rating/leaderboard may be visible to all, whereas special achievements/rewards are for club members. An under-15 restriction is floated. | Later statement supersedes earlier conflict, but needs approval |
| 19:20–19:33 | Share maintainable source code through GitHub for later development. | Operational intent |
| 22:07–22:26 | Use club logo or mascot if assets are provided. | Optional |
| 22:32–22:54 | Roblox/game-style digital rewards. | Optional brainstorming |
| 23:08–23:35 | Twitter-like discussion posts, book reviews and full-text online reading. | Brainstorming; ebook rights and moderation unknown |

## 3. Gaps and inconsistencies

1. **Subscriptions:** website currently describes monthly and quarterly plans and a free first month; audio ASR indicates a different longer plan. No payment requirements are approved.
2. **Ages:** initial hackathon summary said 7–13; public website includes groups 7–8, 9–11, 12–15; meeting floated achievements through age 15. Distinguish program cohorts from account eligibility.
3. **Leaderboards:** both restricted and public variants were discussed. Later statement leans toward visible ranking + club-only rewards, but child profile visibility remains undecided.
4. **Children and guardians:** account creation, parental approval, visibility, moderation and retention have not been decided. No real minors' information in test data.
5. **Membership:** invite code was only suggested; actual validation, revocation and anti-abuse not designed.
6. **Books:** no legal basis for full copyrighted texts in the platform; the club does not provide digital books. Recommend metadata-only catalog in demo unless rights are confirmed.
7. **Recommendation inputs, languages, brand materials, business KPIs, official evaluation criteria:** not yet confirmed.
8. **Transcription uncertainty:** several mixed-language passages are fragmented; confirm decisive statements directly with the partner.

## 4. Recommended hackathon MVP — proposed, not approved

**Hypothesis:** open mobile-first reading journal, with club-specific benefits supporting engagement and membership.

Demo journey: select book from a small legitimate catalog → add to reading diary → update reading progress → view statistics → switch to verified club-member demo profile → unlock one special achievement and one upcoming activity/reminder. Child profile remains private by default. Use synthetic user data.

- **P0 candidates:** responsive UI, simple demo account(s), short book catalog, add-to-shelf, progress/completion, membership distinction, one reward and safe privacy defaults.
- **P1 candidates:** moderated short reviews, leaderboard if visibility policy is approved, lightweight genre recommendations, club events.
- **Defer:** full ebook reader, real subscription billing, native app store release, sophisticated AI, Roblox integrations and one-to-one mentor messaging.
- **Technical suggestion, NOT decision:** installable PWA to demonstrate on phones and laptops without native distribution.

## 5. Partner questions / decision gates

1. Which single business outcome has priority: acquisition, retention, remote scaling or mentor workload? Baseline metric?
2. Precisely which functions are general vs members-only, and which rankings/profile fields can be public?
3. Who manages minor accounts and moderates discussion? Is parent-child linkage required in MVP?
4. What constitutes verified reading; how do already-existing awards work?
5. Who validates memberships, manages club events, maintains the catalog?
6. Is a PWA acceptable? Can they share branding, book metadata/covers and sample content with usage rights?
7. Are subscription payments explicitly out of scope, handled by the existing website, or a required deliverable?

**Next:** obtain answers and mark [CONFIRMED] / [ASSUMPTION] / [UNKNOWN], approve one demo flow, then draft Spec Kit specification and review shared contracts before implementation.
