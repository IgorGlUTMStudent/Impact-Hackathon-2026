"""Mascot script for Gustul Cărților (P0 fixed translatable script).

Owner: Denis (Antigravity).
Contracts: specs/001-reading-diary-mvp/contracts/routes.md § Mascot script
Requirements: FR-031 (fixed script), FR-032 (no guilt or pressure messages).
"""

from typing import Final
from django.utils.translation import gettext as _

from .viewmodels import MascotLine, MascotMood


# Fixed translatable templates and associated moods for all canonical events
MASCOT_SCRIPTS: Final[dict[str, tuple[str, MascotMood]]] = {
    "welcome": (
        _("Salut! Hai să alegem o carte."),
        "happy",
    ),
    "progress_saved": (
        _("Bravo! Ai ajuns la pagina {page}."),
        "cheer",
    ),
    "book_finished": (
        _("Ai terminat cartea! Ce aventură!"),
        "cheer",
    ),
    "achievement": (
        _("Ai deblocat «{title}»!"),
        "cheer",
    ),
    "member_hint": (
        _("Insigna asta e pentru membrii clubului."),
        "think",
    ),
    "error": (
        _("Hmm, verifică numărul paginii."),
        "oops",
    ),
    "offline": (
        _("Nu am internet acum. Încercăm mai târziu?"),
        "oops",
    ),
}


def get_mascot_line(key: str, **kwargs) -> MascotLine:
    """Return a MascotLine dataclass instance with interpolated parameters.

    Unknown keys fall back gracefully to the neutral 'welcome' line.
    No dynamic LLM text generation at runtime.
    """
    if key not in MASCOT_SCRIPTS:
        key = "welcome"

    template, mood = MASCOT_SCRIPTS[key]

    try:
        text = template.format(**kwargs) if kwargs else template
    except (KeyError, IndexError, ValueError):
        text = template

    return MascotLine(key=key, text=text, mood=mood)

