"""Child-mode views for Gustul Cărților.

Owner: Denis (Antigravity).
Contracts:
- specs/001-reading-diary-mvp/contracts/routes.md § Route 1 (Child Home /copil/)
- specs/001-reading-diary-mvp/contracts/authorization.md
"""

from django.db import models
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.accounts.authz import current_reader, is_child_mode, is_htmx, login_required
from apps.club.models import AchievementGrant
from apps.club.services import is_member
from apps.core.mascot import get_mascot_line
from apps.core.viewmodels import BookVM, ChildVM, GrantVM, ShelfEntryVM, percent
from apps.library.models import ShelfEntry


@require_GET
@login_required
def child_home(request):
    """Child home dashboard (/copil/).

    Context (routes.md):
    - child: ChildVM
    - current_entry: ShelfEntryVM | None
    - mascot: MascotLine
    - is_member: bool
    - recent_grants: list[GrantVM]

    Security:
    - Fails closed for adult mode (403 Forbidden).
    - Requires active authenticated child session via ChildModeMiddleware + current_reader.
    - Sensitive child data protected with Cache-Control: private, no-store.
    """
    if not is_child_mode(request):
        # Adult reader cannot browse as child; fail closed
        return HttpResponseForbidden("Acces permis doar în modul copil.")

    reader = current_reader(request)
    child = reader.child

    child_vm = ChildVM(
        public_id=child.public_id,
        nickname=child.nickname,
        avatar=child.avatar,
        age_band=child.age_band,
    )

    # Deterministic current book selection:
    # 1. Books actively in progress ("reading") take precedence over finished
    # 2. Most recently added first (-added_at)
    # 3. Stable tie-breaker (-id)
    entry_model = (
        ShelfEntry.objects.filter(reader=reader)
        .select_related("book")
        .order_by(
            models.Case(
                models.When(status="reading", then=0),
                default=1,
                output_field=models.IntegerField(),
            ),
            "-added_at",
            "-id",
        )
        .first()
    )

    current_entry_vm = None
    if entry_model is not None:
        book = entry_model.book
        book_vm = BookVM(
            public_id=book.public_id,
            title=book.title,
            author=book.author,
            page_count=book.page_count,
            cover_color=book.cover_color,
            cover_emoji=book.cover_emoji,
            genre=book.genre,
            age_band=book.age_band,
        )
        current_entry_vm = ShelfEntryVM(
            public_id=entry_model.public_id,
            book=book_vm,
            current_page=entry_model.current_page,
            page_count=book.page_count,
            percent=percent(entry_model.current_page, book.page_count),
            status=entry_model.status,
        )

    # Recent achievements (up to 3 most recent)
    recent_grants_qs = (
        AchievementGrant.objects.filter(reader=reader)
        .select_related("achievement")
        .order_by("-granted_at", "-id")[:3]
    )
    recent_grants = [
        GrantVM(
            code=g.achievement.code,
            title=g.achievement.title,
            icon=g.achievement.icon,
            granted_at=g.granted_at,
            members_only=g.achievement.members_only,
        )
        for g in recent_grants_qs
    ]

    context = {
        "child": child_vm,
        "current_entry": current_entry_vm,
        "mascot": get_mascot_line("welcome"),
        "is_member": is_member(reader),
        "recent_grants": recent_grants,
    }

    response = render(request, "child/home.html", context)
    # Crucial security requirement: never cache personal child profile data
    response["Cache-Control"] = "private, no-store, must-revalidate"
    return response
