# Data model (proposal — shared contract, decision gate)

**Status**: proposed for review; becomes the single source of truth once PR M0-1 (schema) merges. Any later change is a decision gate (constitution §III).

Conventions: Django ORM, integer primary keys internally, **UUID `public_id`** on every object referenced in URLs (no sequential IDs in URLs). All timestamps UTC. `on_delete` noted per FK.

## Entity overview

```mermaid
erDiagram
    Account ||--o| Reader : "self-reader (0..1)"
    Account ||--o{ ChildProfile : "guardian of"
    ChildProfile ||--|| Reader : "has"
    Reader ||--o{ ShelfEntry : owns
    Book ||--o{ ShelfEntry : "is on"
    ShelfEntry ||--o{ ProgressEvent : logs
    Reader ||--o{ ClubMembership : entitled
    MembershipCode |o--o| ClubMembership : "redeemed into"
    Reader ||--o{ AchievementGrant : earns
    Achievement ||--o{ AchievementGrant : "granted as"
```

## Tables

### `accounts.Account` (custom user model — must exist before the first migration)

| Field | Type | Rules |
|---|---|---|
| id | PK | |
| email | email, unique, case-insensitive | login identifier |
| password | hash | Django hasher |
| display_name | str ≤ 40 | shown only to the account holder |
| ui_language | enum `ro`/`ru` | default `ro` |
| pin_hash | str, nullable | set before first child mode (FR-004); PIN attempts are counted in `accounts.Throttle` (scope `pin`) |
| is_staff | bool | club admin; **not** a reader role |
| date_joined | datetime | |

### `accounts.ChildProfile`

| Field | Type | Rules |
|---|---|---|
| id, public_id | PK, UUID unique | |
| guardian | FK Account, `CASCADE` | set from session only; never from form input |
| nickname | str 2–20 | not required to be a real name; no uniqueness across families |
| age_band | enum `7-8`, `9-11`, `12-15` | |
| avatar | enum (fixed list of ~8 drawn avatars) | no photo upload |
| ui_language | enum `ro`/`ru` | |
| created_at | datetime | |

Invariant: max 6 children per guardian (abuse limit) `[ASSUMPTION]`.

### `accounts.Reader`

| Field | Type | Rules |
|---|---|---|
| id, public_id | PK, UUID | |
| kind | enum `adult`/`child` | |
| account | OneToOne Account, nullable, `CASCADE` | set iff `kind=adult` |
| child | OneToOne ChildProfile, nullable, `CASCADE` | set iff `kind=child` |

DB check constraint: exactly one of `account`, `child` is non-null and matches `kind`. Created automatically with the account (lazily on first shelf action) or with the child.

**Ownership rule (single function, `accounts/authz.py`)**: an authenticated adult `A` may act on reader `R` iff `R.account == A` or `R.child.guardian == A`. In child mode the only permitted reader is `session.active_child_reader`.

### `accounts.Throttle` (failed-attempt counters for login, PIN and code redemption)

| Field | Type | Rules |
|---|---|---|
| id | PK | |
| scope | enum `login`/`pin`/`redeem` | three independent limits (see [authorization.md](./contracts/authorization.md#brute-force-limits-three-separate-throttles)) |
| key_hash | str | SHA-256 of the scope key: normalized email for `login` (also for unknown emails, so responses do not reveal which accounts exist); account id for `pin` and `redeem` |
| failures | int ≥ 0 | failures in the current window |
| window_started_at | datetime | start of the counting window |
| locked_until | datetime, nullable | while `now < locked_until` every attempt is refused, even a correct one |

`UNIQUE (scope, key_hash)`. Read and updated only through `accounts/throttle.py` (`check(scope, key)`, `record_failure(scope, key)`, `reset(scope, key)`), inside the same short write transaction as the attempt. Stored in the database (not in a per-process cache), so counters survive a worker restart and are shared by every process.

### `library.Book`

| Field | Type | Rules |
|---|---|---|
| id, public_id | PK, UUID | |
| title, author | str | |
| language | enum `ro`/`ru`/`en` | |
| page_count | int | `CHECK page_count BETWEEN 1 AND 2000` |
| age_band | enum, nullable | recommendation only |
| genre | enum (small fixed list) | |
| cover_color, cover_emoji | str | generated cover; no copyrighted images in P0 |
| source_note | str | where the metadata came from / rights note |
| is_active | bool | admin can hide |

### `library.ShelfEntry`

| Field | Type | Rules |
|---|---|---|
| id, public_id | PK, UUID | |
| reader | FK Reader, `CASCADE` | |
| book | FK Book, `PROTECT` | |
| current_page | int | `CHECK current_page >= 0`; `<= book.page_count` enforced in service + test (cross-table) |
| status | enum `reading`/`finished` | |
| added_at, finished_at | datetime, nullable | `finished_at` set iff `status=finished` (check constraint) |

`UNIQUE (reader, book)` → duplicate add is a no-op (FR-011). Re-reading a finished book: deferred.

### `library.ProgressEvent` (append-only)

| Field | Type | Rules |
|---|---|---|
| id | PK | |
| entry | FK ShelfEntry, `CASCADE` | |
| reader | FK Reader, `CASCADE` | denormalized for the unique key and stats |
| from_page, to_page | int | |
| kind | enum `progress`/`finish` | |
| request_id | UUID | client-generated per submit |
| created_at | datetime | |

`UNIQUE (reader, request_id)` → idempotency (FR-014). Never updated or deleted except by cascade. `from_page` is the value the server read inside the write transaction, never a client value. The stored `(entry, kind, to_page)` is the fingerprint used to tell a true replay from a reused `request_id` with different data (see *Concurrency and idempotency*).

### `club.ClubMembership`

| Field | Type | Rules |
|---|---|---|
| id | PK | |
| reader | FK Reader, `CASCADE` | |
| status | enum `active`/`revoked` | |
| valid_from, valid_until | datetime | `CHECK valid_until > valid_from` |
| source | enum `admin`/`code` | |
| granted_by | FK Account (staff), nullable, `SET_NULL` | |
| code | OneToOne MembershipCode, nullable | |
| revoked_at, revoked_by | nullable | |

`is_member(reader, now)` = exists row with `status=active AND valid_from <= now < valid_until`. Computed per request; **never stored in the session or sent as a trusted client value**. Overlapping memberships allowed (renewal = new row).

### `club.MembershipCode`

| Field | Type | Rules |
|---|---|---|
| id | PK | |
| code_hash | str unique | SHA-256 of the normalized code; plaintext shown once in admin |
| label | str | e.g. "Grupa 9–11, noiembrie" (no child names) |
| expires_at | datetime | |
| membership_days | int | default 90 `[ASSUMPTION — G3]` |
| created_by | FK Account (staff), `PROTECT` | |
| redeemed_at, redeemed_for | datetime nullable, FK Reader nullable, `SET_NULL` | single use: redemption sets both atomically (`UPDATE … WHERE redeemed_at IS NULL`). DB check: `redeemed_for` set ⇒ `redeemed_at` set. If the reader is later deleted, `redeemed_for` becomes NULL and the code stays used (M0 correction, PR for Issue #10) |

### `club.Achievement` (seeded definitions)

| Field | Type | Rules |
|---|---|---|
| id, code | PK, slug unique | e.g. `first-book`, `pages-100`, `club-reader` |
| title, description | translatable str | |
| rule | enum `books_finished_gte`, `pages_total_gte`, `shelf_size_gte` | |
| threshold | int ≥ 1 | |
| members_only | bool | |
| icon | str | static asset name |

P0 seed: `first-book` (books_finished ≥ 1, general), `pages-100` (pages_total ≥ 100, general), `club-reader` (books_finished ≥ 1, **members_only**).

### `club.AchievementGrant`

| Field | Type | Rules |
|---|---|---|
| id | PK | |
| reader | FK Reader, `CASCADE` | |
| achievement | FK Achievement, `PROTECT` | |
| granted_at | datetime | |
| was_member | bool | snapshot for audit |

`UNIQUE (reader, achievement)` (FR-024). Created only by `club.services.evaluate_achievements(reader)`.

### `club.ClubActivity`

| Field | Type | Rules |
|---|---|---|
| id | PK | |
| title, description, place | translatable str | |
| starts_at | datetime | |
| is_published | bool | |

Visible only on the members-only page.

## Domain services (the only code allowed to write these tables)

| Service | Module | Writes | Transaction | Notes |
|---|---|---|---|---|
| `add_to_shelf(reader, book)` | `library/services.py` | ShelfEntry | atomic, `get_or_create` | idempotent |
| `record_progress(reader, entry, page, request_id)` | `library/services.py` | ShelfEntry, ProgressEvent, then calls `evaluate_achievements` | one short write transaction (see below) | returns `ProgressResult(entry, new_grants, replayed: bool)`; raises `RequestIdConflict` (→ 409) or `LockTimeout` (→ 503) |
| `finish_book(reader, entry, request_id)` | `library/services.py` | same | same | sets `current_page = page_count` |
| `reader_stats(reader)` | `library/stats.py` | — | read | books_on_shelf, books_finished, pages_total (= Σ current_page), pages_7d (Σ positive deltas in events, last 7 days) |
| `redeem_code(actor, reader, raw_code)` | `club/services.py` | MembershipCode, ClubMembership, then `evaluate_achievements` | atomic, conditional update | generic error on any failure |
| `evaluate_achievements(reader)` | `club/services.py` | AchievementGrant | inside caller's transaction | `is_member` checked at evaluation time; `get_or_create` under unique key |

## Concurrency and idempotency (P0 policy)

**What the database really guarantees**

| Guarantee | SQLite (demo) | PostgreSQL (if chosen) |
|---|---|---|
| `UNIQUE` / `CHECK` constraints | ✅ enforced | ✅ enforced |
| A transaction commits completely or not at all | ✅ | ✅ |
| `select_for_update()` row locks | ❌ **no effect** on SQLite ([Django docs](https://docs.djangoproject.com/en/5.2/ref/models/querysets/#select-for-update)) | ✅ row lock |
| Only one write transaction at a time | ✅ whole-database write lock (one writer, readers continue) | ❌ not needed: row locks instead |
| High write throughput / many simultaneous writers | ❌ not claimed | not measured; not claimed |

**Chosen policy (one design, no queues, workers or distributed locks)**

1. SQLite settings: `OPTIONS = {"transaction_mode": "IMMEDIATE", "timeout": 5}` (Django ≥ 5.1). `IMMEDIATE` takes the database write lock at `BEGIN`, so the read-check-write sequence inside one service call cannot interleave with another writer. A waiting writer blocks up to 5 s; after that SQLite raises "database is locked". `ATOMIC_REQUESTS` stays off: only the service functions open transactions, and they hold no network I/O or template rendering.
2. `record_progress` / `finish_book` run in one `transaction.atomic()`:
   1. look up `ProgressEvent(reader, request_id)`;
      - **same `request_id`, same `(entry, kind, to_page)`** → return the stored result with `replayed=True`; nothing is written and no grant is created;
      - **same `request_id`, different data** → raise `RequestIdConflict`; the view answers **409** and nothing changes;
   2. re-read the entry by `(public_id, reader)`. In code this is `select_for_update()`, which locks the row on PostgreSQL and has no effect on SQLite, where step 1 (IMMEDIATE) already serializes writers;
   3. validate the range and the `reading` status against the re-read row; set `from_page` from that row;
   4. insert the event (the unique key is the last line of defence: an `IntegrityError` there is handled like a replay), update the entry, call `evaluate_achievements`;
   5. commit. The success partial is rendered only after commit.
3. **Two different `request_id`s on the same entry** (two tabs or devices): both are accepted in **commit order** (last committed wins for `current_page`). The order in which the client sent them is not preserved and is not promised. Each event stores the `from_page` it actually replaced, so the log and `pages_7d` stay consistent. `finished` is terminal: after one request finishes the book, a later progress or finish request with another ID gets **422 "already finished"**, so "books finished" grows exactly once. No stale-write detection (`expected_page`) in P0. If the demo shows lost updates are a real problem, it is the first thing to add.
4. **Lock timeout**: "database is locked" after the busy timeout → the transaction rolls back → the view answers **503** with the "Nu s-a salvat — încearcă din nou" message. There is no automatic server retry. The user retries manually with the **same** `request_id` (it is only regenerated after a 2xx), so a retry after an unknown outcome can never double-apply.
5. `redeem_code` and `accounts/throttle.py` use the same short IMMEDIATE transactions. Single use of a code is still enforced by the conditional `UPDATE … WHERE redeemed_at IS NULL`.

**Planned tests (all NOT RUN; need a file-based SQLite test DB, because the in-memory test DB cannot be shared between threads)**

| Case | Test | Expected |
|---|---|---|
| (a) same-ID replay | `test_concurrency.py::test_replay_same_request_id_returns_prior_result` | 2nd call `replayed=True`; one event; stats and grants unchanged |
| (a') same ID, different data | `::test_reused_request_id_with_other_page_is_409` | 409; stored page and events unchanged |
| (b) concurrent different IDs | `::test_two_request_ids_same_entry_commit_order` (`TransactionTestCase`, 2 threads) | both commit; `current_page` = the later commit; each `from_page` equals the previous committed value; a finish counted once |
| (b') finish race | `::test_finish_race_counts_once` | one finish event, the other request gets 422, `books_finished` = 1 |
| (c) lock contention | `::test_lock_timeout_returns_503_and_stores_nothing` (another connection holds `BEGIN IMMEDIATE`; timeout lowered for the test) | 503 within the bounded wait; no event; retry with the same ID then succeeds once |

## Seed / demo data (`manage.py seed_demo`, idempotent)

- 1 staff account (`admin@demo.local`), 2 guardian accounts, children "Mia" (9–11) and "Alex" (7–8), 1 adult reader without children — all synthetic.
- 12 books: public-domain Romanian children's classics (metadata only, generated covers), page counts set explicitly.
- Achievements as above; 2 published club activities.
- No membership codes are seeded (M0 correction): codes are issued by staff through the PR-5 admin action, which shows the plaintext once. Nothing secret is ever printed by `seed_demo`.
- `--reset` deletes only `@demo.local` accounts (cascading to their children, shelves, progress and grants) and refuses to run if any non-demo account exists.
- Passwords/PINs for demo accounts come from environment variables, never committed.
