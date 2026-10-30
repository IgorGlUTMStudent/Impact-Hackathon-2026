"""Identity/ownership checks (contracts/authorization.md). The only way views get a reader or a child.

Public interface (frozen for PR-3/4/5, Issue #14):

    login_required(view)                       decorator: anonymous -> 302 login?next=, HTMX -> 401 + HX-Redirect
    is_child_mode(request) -> bool
    current_reader(request) -> Reader          adult mode: own reader; child mode: active child's reader,
                                               re-validated against request.user. Raises PermissionDenied if none.
    get_child_for_guardian(request, public_id) -> ChildProfile   own child or Http404
    get_entry_for_reader(reader, public_id)    -> ShelfEntry     reader's entry or Http404

Session keys (written only by accounts.views): session["mode"] = "child", session["active_child"] = str(ChildProfile.public_id).
"""

from functools import wraps
from urllib.parse import urlsplit

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpResponse

from apps.library.models import ShelfEntry

from .models import ChildProfile, Reader

MODE_KEY, ACTIVE_CHILD_KEY = "mode", "active_child"


def is_htmx(request):
    return request.headers.get("HX-Request") == "true"


def is_child_mode(request):
    return request.session.get(MODE_KEY) == "child"


def login_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.user.is_authenticated:
            return view(request, *args, **kwargs)
        next_path = request.get_full_path()
        if is_htmx(request):
            # Come back to the page that sent the request, not to the mutation URL.
            next_path = urlsplit(request.headers.get("HX-Current-URL", "")).path or next_path
        response = redirect_to_login(next_path)
        if is_htmx(request):
            return HttpResponse(status=401, headers={"HX-Redirect": response["Location"]})
        return response

    return wrapped


def active_child_reader(request):
    """Child-mode reader, or None if the session's child is missing, deleted or not this guardian's."""
    if not request.user.is_authenticated:
        return None
    try:
        return Reader.objects.select_related("child").get(
            child__public_id=request.session.get(ACTIVE_CHILD_KEY), child__guardian=request.user
        )
    except (Reader.DoesNotExist, ValidationError, ValueError):
        return None


def current_reader(request):
    if not request.user.is_authenticated:
        raise PermissionDenied
    if is_child_mode(request):
        reader = active_child_reader(request)
        if reader is None:
            raise PermissionDenied  # fail closed: never fall back to the adult's reader
        return reader
    # get_or_create: accounts made by createsuperuser have no reader yet; OneToOne keeps it to exactly one.
    reader, _ = Reader.objects.get_or_create(account=request.user, defaults={"kind": Reader.ADULT})
    return reader


def get_child_for_guardian(request, public_id):
    if not request.user.is_authenticated:
        raise Http404
    try:
        return ChildProfile.objects.get(public_id=public_id, guardian=request.user)
    except (ChildProfile.DoesNotExist, ValidationError, ValueError):
        raise Http404 from None


def get_entry_for_reader(reader, public_id):
    try:
        return ShelfEntry.objects.select_related("book").get(public_id=public_id, reader=reader)
    except (ShelfEntry.DoesNotExist, ValidationError, ValueError):
        raise Http404 from None
