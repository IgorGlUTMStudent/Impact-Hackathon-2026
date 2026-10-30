import uuid

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.test import RequestFactory

from apps.accounts import authz
from apps.accounts.models import Account, Reader
from apps.library.models import Book, ShelfEntry

from .conftest import make_child, make_guardian

pytestmark = pytest.mark.django_db


def request_for(user, **session):
    request = RequestFactory().get("/")
    request.user = user
    request.session = dict(session)
    return request


def child_session(child):
    return {"mode": "child", "active_child": str(child.public_id)}


def test_adult_mode_returns_own_reader(guardian):
    assert authz.current_reader(request_for(guardian)) == guardian.reader


def test_adult_reader_created_once_for_accounts_without_one():
    staff = Account.objects.create_superuser("admin@demo.local", "x-strong-pass-1", display_name="Admin")
    first = authz.current_reader(request_for(staff))
    assert first.kind == Reader.ADULT and authz.current_reader(request_for(staff)) == first


def test_child_mode_returns_active_child_reader(guardian, child):
    assert authz.current_reader(request_for(guardian, **child_session(child))) == child.reader


def test_child_mode_with_foreign_child_fails_closed(guardian):
    other_child = make_child(make_guardian("altul@demo.local"))
    with pytest.raises(PermissionDenied):
        authz.current_reader(request_for(guardian, **child_session(other_child)))


@pytest.mark.parametrize("active_child", [None, "", "not-a-uuid", str(uuid.uuid4())])
def test_child_mode_with_missing_or_bad_child_fails_closed(guardian, active_child):
    with pytest.raises(PermissionDenied):
        authz.current_reader(request_for(guardian, mode="child", active_child=active_child))


def test_deleted_child_fails_closed_never_adult_reader(guardian, child):
    session = child_session(child)
    child.delete()
    with pytest.raises(PermissionDenied):
        authz.current_reader(request_for(guardian, **session))


def test_anonymous_has_no_reader():
    with pytest.raises(PermissionDenied):
        authz.current_reader(request_for(AnonymousUser()))


def test_get_child_for_guardian_owner_only(guardian, child):
    assert authz.get_child_for_guardian(request_for(guardian), child.public_id) == child
    assert authz.get_child_for_guardian(request_for(guardian), str(child.public_id)) == child
    other = make_guardian("altul@demo.local")
    for user, public_id in [(other, child.public_id), (AnonymousUser(), child.public_id),
                            (guardian, uuid.uuid4()), (guardian, "nonsense")]:
        with pytest.raises(Http404):
            authz.get_child_for_guardian(request_for(user), public_id)


def test_get_entry_for_reader_owner_only(guardian, child):
    book = Book.objects.create(title="T", author="A", language="ro", page_count=100, genre="poveste")
    entry = ShelfEntry.objects.create(reader=child.reader, book=book)
    assert authz.get_entry_for_reader(child.reader, entry.public_id) == entry
    for reader, public_id in [(guardian.reader, entry.public_id), (child.reader, uuid.uuid4()), (child.reader, "x")]:
        with pytest.raises(Http404):
            authz.get_entry_for_reader(reader, public_id)
