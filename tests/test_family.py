import pytest

from apps.accounts.models import Account, ChildProfile, Reader

from .conftest import PASSWORD, make_child, make_guardian

pytestmark = pytest.mark.django_db
NEW_CHILD = {"nickname": "Alex", "age_band": "7-8", "avatar": "owl"}


# --- signup ---------------------------------------------------------------------------------------------------------

def signup(client, **overrides):
    return client.post("/cont/inregistrare/", {"email": "Nou@Demo.Local", "display_name": "Ana",
                                                "password": PASSWORD, **overrides})


def test_signup_creates_account_and_one_adult_reader_and_logs_in(client):
    response = signup(client)
    assert response.status_code == 302 and response["Location"] == "/panou/"
    account = Account.objects.get()
    assert account.email == "nou@demo.local" and account.check_password(PASSWORD)
    assert Reader.objects.get().account == account and Reader.objects.get().kind == Reader.ADULT
    assert client.session["_auth_user_id"] == str(account.pk)


def test_signup_existing_email_any_case_is_422(client, guardian):
    response = signup(client, email="PARINTE@demo.local")
    assert response.status_code == 422
    assert Account.objects.count() == 1


def test_signup_ignores_staff_fields(client):
    signup(client, is_staff="on", is_superuser="on")
    account = Account.objects.get()
    assert not account.is_staff and not account.is_superuser


@pytest.mark.parametrize("password", ["123", "password", "12345678901", "nou@demo.local"])
def test_signup_applies_django_password_validators(client, password):
    assert signup(client, password=password).status_code == 422
    assert not Account.objects.exists()


# --- family CRUD ----------------------------------------------------------------------------------------------------

def test_create_child_for_session_guardian_with_child_reader(adult_client, guardian):
    other = make_guardian("altul@demo.local")
    response = adult_client.post("/familie/", {**NEW_CHILD, "guardian": other.pk})
    assert response.status_code == 302 and response["Location"] == "/familie/"
    child = ChildProfile.objects.get()
    assert child.guardian == guardian  # never from the form
    assert child.reader.kind == Reader.CHILD


@pytest.mark.parametrize("bad", [{"nickname": "A"}, {"nickname": "x" * 21}, {"age_band": "3-4"}, {"avatar": "dragon"}])
def test_create_child_validation_is_422(adult_client, bad):
    assert adult_client.post("/familie/", {**NEW_CHILD, **bad}).status_code == 422
    assert not ChildProfile.objects.exists()


def test_child_limit_is_6(adult_client, guardian):
    for i in range(6):
        assert adult_client.post("/familie/", {**NEW_CHILD, "nickname": f"Copil{i}"}).status_code == 302
    response = adult_client.post("/familie/", NEW_CHILD)
    assert response.status_code == 422
    assert guardian.children.count() == 6


def test_family_lists_only_own_children(adult_client, child):
    make_child(make_guardian("altul@demo.local"), nickname="Străin")
    children = adult_client.get("/familie/").context["children"]
    assert [c.nickname for c in children] == ["Mia"]


def test_rename_own_child(adult_client, child):
    assert adult_client.post(f"/familie/{child.public_id}/editeaza/", {"nickname": "Mimi"}).status_code == 302
    child.refresh_from_db()
    assert child.nickname == "Mimi"


def test_rename_invalid_is_422_and_unchanged(adult_client, child):
    assert adult_client.post(f"/familie/{child.public_id}/editeaza/", {"nickname": "M"}).status_code == 422
    child.refresh_from_db()
    assert child.nickname == "Mia"


def test_delete_needs_confirm(adult_client, child):
    assert adult_client.post(f"/familie/{child.public_id}/sterge/").status_code == 422
    assert ChildProfile.objects.exists()
    assert adult_client.post(f"/familie/{child.public_id}/sterge/", {"confirm": "1"}).status_code == 302
    assert not ChildProfile.objects.exists() and not Reader.objects.filter(kind=Reader.CHILD).exists()
    assert adult_client.post(f"/familie/{child.public_id}/sterge/", {"confirm": "1"}).status_code == 404


def test_foreign_child_is_404_for_every_family_mutation(adult_client):
    foreign = make_child(make_guardian("altul@demo.local"), nickname="Străin")
    base = f"/familie/{foreign.public_id}"
    assert adult_client.post(f"{base}/editeaza/", {"nickname": "Hacked"}).status_code == 404
    assert adult_client.post(f"{base}/sterge/", {"confirm": "1"}).status_code == 404
    assert adult_client.post(f"{base}/mod-copil/").status_code == 404
    foreign.refresh_from_db()
    assert foreign.nickname == "Străin"


def test_family_mutations_require_post(adult_client, child):
    assert adult_client.get(f"/familie/{child.public_id}/sterge/").status_code == 405
    assert ChildProfile.objects.exists()


# --- PIN setup ------------------------------------------------------------------------------------------------------

def set_pin(client, **overrides):
    return client.post("/familie/pin/", {"pin": "1357", "pin_confirm": "1357", "password": PASSWORD, **overrides})


def test_set_pin_hashes_and_never_echoes(adult_client, guardian):
    response = set_pin(adult_client)
    assert response.status_code == 302
    guardian.refresh_from_db()
    assert guardian.pin_hash.startswith("pbkdf2_sha256$") and "1357" not in guardian.pin_hash


@pytest.mark.parametrize("bad", [{"pin_confirm": "1358"}, {"password": "wrong"}, {"pin": "12", "pin_confirm": "12"},
                                 {"pin": "1234567", "pin_confirm": "1234567"}, {"pin": "12a4", "pin_confirm": "12a4"}])
def test_set_pin_rejects_bad_input(adult_client, guardian, bad):
    before = guardian.pin_hash
    response = set_pin(adult_client, **bad)
    assert response.status_code == 422
    assert f'value="{bad.get("pin", "1357")}"' not in response.content.decode()  # PIN never echoed
    guardian.refresh_from_db()
    assert guardian.pin_hash == before
