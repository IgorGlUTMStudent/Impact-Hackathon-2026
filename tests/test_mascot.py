import pytest

from apps.core.mascot import MASCOT_SCRIPTS, get_mascot_line
from apps.core.viewmodels import MascotLine


def test_all_canonical_keys_defined():
    expected_keys = {
        "welcome",
        "progress_saved",
        "book_finished",
        "achievement",
        "member_hint",
        "error",
        "offline",
    }
    assert set(MASCOT_SCRIPTS.keys()) == expected_keys


def test_get_mascot_line_welcome():
    line = get_mascot_line("welcome")
    assert isinstance(line, MascotLine)
    assert line.key == "welcome"
    assert line.mood == "happy"
    assert "Salut!" in line.text


def test_get_mascot_line_progress_saved_interpolation():
    line = get_mascot_line("progress_saved", page=35)
    assert line.key == "progress_saved"
    assert line.mood == "cheer"
    assert "pagina 35" in line.text


def test_get_mascot_line_achievement_interpolation():
    line = get_mascot_line("achievement", title="Cititor de Club")
    assert line.key == "achievement"
    assert line.mood == "cheer"
    assert "«Cititor de Club»" in line.text


def test_get_mascot_line_member_hint():
    line = get_mascot_line("member_hint")
    assert line.key == "member_hint"
    assert line.mood == "think"
    assert "membrii clubului" in line.text


def test_get_mascot_line_error():
    line = get_mascot_line("error")
    assert line.key == "error"
    assert line.mood == "oops"


def test_get_mascot_line_offline():
    line = get_mascot_line("offline")
    assert line.key == "offline"
    assert line.mood == "oops"
    assert "Nu am internet acum" in line.text


def test_get_mascot_line_unknown_fallback():
    line = get_mascot_line("non_existent_key")
    assert line.key == "welcome"
    assert line.mood == "happy"


def test_no_guilt_or_pressure_messages():
    forbidden_terms = ["rău", "trist", "leneș", "trebuie", "vinovat", "dezamăgit", "sad", "guilt"]
    for key, (template, _) in MASCOT_SCRIPTS.items():
        lower_text = template.lower()
        for term in forbidden_terms:
            assert term not in lower_text, f"Forbidden guilt term '{term}' found in {key}: {template}"

