from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import Resolver404, resolve

from .authz import ACTIVE_CHILD_KEY, MODE_KEY, active_child_reader, is_child_mode, is_htmx

# authorization.md: the only routes a child-mode session may reach. Matched on view_name (namespaced),
# so admin's "admin:login" never matches; every route not listed here, including future ones, is refused.
CHILD_ALLOWED = frozenset({
    "child_home", "catalog", "book_detail", "add_to_shelf", "my_shelf", "shelf_entry", "record_progress",
    "finish_book", "achievements", "club_corner", "pin_gate", "logout", "offline", "manifest", "sw",
})
# Reachable even when the session's child is gone: the guardian must still be able to unlock or sign out.
ALWAYS_ALLOWED = frozenset({"pin_gate", "logout"})


class ChildModeMiddleware:
    """Deny by default in child mode. Must run after AuthenticationMiddleware."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if is_child_mode(request):
            if not request.user.is_authenticated:
                # Adult session already gone: nothing left to protect, and login must stay reachable.
                request.session.pop(MODE_KEY, None)
                request.session.pop(ACTIVE_CHILD_KEY, None)
            elif not self._allowed(request):
                if is_htmx(request):
                    return HttpResponse(status=403)
                return redirect("pin_gate")
        return self.get_response(request)

    def _allowed(self, request):
        try:
            name = resolve(request.path_info, getattr(request, "urlconf", None)).view_name
        except Resolver404:
            return False
        if name in ALWAYS_ALLOWED:
            return True
        # A deleted or foreign active child fails closed: only the PIN gate and logout remain.
        return name in CHILD_ALLOWED and active_child_reader(request) is not None
