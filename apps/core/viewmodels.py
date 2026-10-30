"""View models shared by adult/ and child/ templates (contracts/routes.md § Template context contracts).

Owner: Arsenii. Ask for new fields in the PR thread instead of editing here.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

MascotMood = Literal["happy", "cheer", "think", "oops"]


@dataclass(frozen=True)
class BookVM:
    public_id: UUID
    title: str
    author: str
    page_count: int
    cover_color: str
    cover_emoji: str
    genre: str
    age_band: str | None


@dataclass(frozen=True)
class ShelfEntryVM:
    public_id: UUID
    book: BookVM
    current_page: int
    page_count: int
    percent: int  # 0–100
    status: Literal["reading", "finished"]


@dataclass(frozen=True)
class StatsVM:
    books_on_shelf: int
    books_finished: int
    pages_total: int
    pages_7d: int


@dataclass(frozen=True)
class GrantVM:
    code: str
    title: str
    icon: str
    granted_at: datetime
    members_only: bool


@dataclass(frozen=True)
class AchievementVM:
    # Used by achievements.html "locked" items; routes.md names it but did not list its fields.
    code: str
    title: str
    icon: str
    members_only: bool


@dataclass(frozen=True)
class ChildVM:
    public_id: UUID
    nickname: str
    avatar: str
    age_band: str


@dataclass(frozen=True)
class MascotLine:
    key: str  # one of the keys in the mascot script (core/mascot.py, PR-8)
    text: str  # already translated
    mood: MascotMood


def percent(current_page, page_count):
    return min(100, round(current_page * 100 / page_count)) if page_count else 0
