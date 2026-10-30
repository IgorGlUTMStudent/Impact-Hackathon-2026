"""Mascot script for Gustul Cărților (P0 fixed translatable script).

Owner: Denis (Antigravity).
Contracts: specs/001-reading-diary-mvp/contracts/routes.md § Mascot script
Requirements: FR-031 (fixed script), FR-032 (no guilt or pressure messages).
"""

from typing import Final
from django.utils.translation import gettext_lazy as _

from .viewmodels import MascotLine, MascotMood


# Fixed translatable templates and associated moods for all canonical events.
# Uses gettext_lazy so translations evaluate at runtime in the active language context.
MASCOT_SCRIPTS: Final[dict[str, tuple[object, MascotMood]]] = {
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

    Translates lazy templates within the currently active language context.
    Unknown keys fall back gracefully to the neutral 'welcome' line.
    No dynamic LLM text generation at runtime.
    """
    if key not in MASCOT_SCRIPTS:
        key = "welcome"

    lazy_template, mood = MASCOT_SCRIPTS[key]
    template_str = str(lazy_template)

    try:
        text = template_str.format(**kwargs) if kwargs else template_str
    except (KeyError, IndexError, ValueError):
        text = template_str

    return MascotLine(key=key, text=text, mood=mood)
