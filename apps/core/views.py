from datetime import datetime, timezone
from uuid import UUID

from django.conf import settings
from django.db import connection
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.template import TemplateDoesNotExist
from django.views.decorators.http import require_GET

from .viewmodels import AchievementVM, BookVM, ChildVM, GrantVM, MascotLine, ShelfEntryVM, StatsVM


@require_GET
def healthz(request):
    """Liveness + DB reachability. Reveals nothing about users or children."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_ok = True
    except Exception:
        db_ok = False
    return JsonResponse({"status": "ok" if db_ok else "degraded", "db": db_ok}, status=200 if db_ok else 503)


def _sample_context():
    # Fixed synthetic values for UI work only; never reads the database.
    book = BookVM(
        public_id=UUID(int=1), title="Capra cu trei iezi", author="Ion Creangă", page_count=120,
        cover_color="#F4A261", cover_emoji="🐐", genre="fairy_tale", age_band="7-8",
    )
    entry = ShelfEntryVM(public_id=UUID(int=2), book=book, current_page=35, page_count=120, percent=29, status="reading")
    stats = StatsVM(books_on_shelf=3, books_finished=1, pages_total=155, pages_7d=35)
    grant = GrantVM(
        code="first-book", title="Prima carte", icon="first-book.svg",
        granted_at=datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc), members_only=False,
    )
    club = AchievementVM(code="club-reader", title="Cititor de Club", icon="club-reader.svg", members_only=True)
    child = ChildVM(public_id=UUID(int=3), nickname="Mia", avatar="fox", age_band="9-11")
    return {
        "child": child,
        "me": {"display_name": "Părinte Demo"},
        "book": book,
        "books": [book],
        "filters": {"age_band": None, "genre": None},
        "shelf_book_ids": {book.public_id},
        "entry": entry,
        "entries": [entry],
        "current_entry": entry,
        "request_id": UUID(int=4),
        "mascot": MascotLine(key="progress_saved", text="Bravo! Ai ajuns la pagina 35.", mood="cheer"),
        "is_member": False,
        "recent_grants": [grant],
        "new_grants": [],
        "errors": [],
        "stats": stats,
        "my_stats": stats,
        "children": [{"child": child, "stats": stats, "current_entry": entry}],
        "grants": [grant],
        "earned": [grant],
        "locked": [{"achievement": club, "members_only": True, "hint": "Insigna asta e pentru membrii clubului."}],
        "memberships": [],
        "activities": [
            {"title": "Seară de povești", "starts_at": datetime(2026, 11, 15, 16, 0, tzinfo=timezone.utc), "place": "Online"}
        ],
    }


def template_preview(request, template_name):
    """DEBUG-only renderer of templates/adult|child/* with synthetic context, for parallel UI work."""
    if not settings.DEBUG or not template_name.startswith(("adult/", "child/")) or ".." in template_name:
        raise Http404
    try:
        return render(request, template_name, _sample_context())
    except TemplateDoesNotExist:
        raise Http404
