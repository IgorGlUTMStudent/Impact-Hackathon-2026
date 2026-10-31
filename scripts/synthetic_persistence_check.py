"""Issue #43 G43-S2: cross-process synthetic persistence proof.

The orchestrator creates a disposable file-backed SQLite database outside the
repository and drives four separate Python processes against the same file:

  preflight  verifies the effective Django settings point at the temp DB (before any migration)
  migrate    real ``manage.py migrate --noinput`` subprocess
  seed       synthetic guardian/child/120-page-book fixtures (ORM setup only, no seed_demo)
  writer     logs in through the real login view, enters child mode via the real route,
             adds the book via add_to_shelf and POSTs page 35 through record_progress, then exits
  reader     a NEW process performs its own fresh guardian login and reads 35/120 through
             child_report (and adult_dashboard) without writing anything

The only write path is the production HTTP route; the only bridge between the
writer and the reader is the SQLite file plus a state file of safe IDs and a
SHA-256 of the writer session key (never the key, cookie, password or PIN).

This proves local file persistence across processes. It does NOT prove Render
restart/redeploy durability, PostgreSQL storage or any hosted behaviour; issue
#34 stays open.

Run:  uv run python scripts/synthetic_persistence_check.py
"""

import argparse
import hashlib
import json
import os
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = Path(__file__).resolve()
DB_FILE = "synthetic.sqlite3"
PAGE, BOOK_PAGES = 35, 120

# Child processes must never inherit a host DATABASE_URL/settings module or any
# credential: an inherited value would redirect writes away from the temp DB.
SCRUBBED = (
    "DATABASE_URL",
    "DJANGO_SETTINGS_MODULE",
    "DJANGO_SECRET_KEY",
    "DJANGO_ALLOWED_HOSTS",
    "DEMO_PASSWORD",
    "DEMO_PIN",
    "DJANGO_SUPERUSER_EMAIL",
    "DJANGO_SUPERUSER_PASSWORD",
)

HTMX = {"HTTP_HX_REQUEST": "true"}


def fail(role, reason):
    print(json.dumps({"role": role, "status": "FAIL", "reason": reason}), file=sys.stderr)
    sys.exit(1)


def state_path():
    return Path(os.environ["GC43_TMP"]) / "state.json"


def read_state(role):
    if not state_path().exists():
        fail(role, "state file is missing")
    return json.loads(state_path().read_text(encoding="utf-8"))


def write_state(role, state):
    state_path().write_text(json.dumps(state), encoding="utf-8")


def django_ready(role):
    """Configure Django and abort before any DB access unless settings point at the temp SQLite."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    import django

    django.setup()
    from django.conf import settings

    db = settings.DATABASES["default"]
    name = Path(str(db["NAME"])).resolve()
    expected = Path(os.environ["GC43_DB"]).resolve()
    tmp_dir = Path(os.environ["GC43_TMP"]).resolve()
    if db["ENGINE"] != "django.db.backends.sqlite3" or name != expected:
        fail(role, f"effective DB is {db['ENGINE']} {name}, expected the disposable temp SQLite")
    if tmp_dir not in name.parents:
        fail(role, f"DB {name} is outside the temp dir")
    if REPO_ROOT in name.parents or name == (REPO_ROOT / "db.sqlite3").resolve():
        fail(role, f"DB {name} is inside the repository")
    return settings


def test_client():
    # setup_test_environment only appends 'testserver' to ALLOWED_HOSTS for this
    # process; it never touches the database or the real session store.
    from django.test import Client
    from django.test.utils import setup_test_environment

    setup_test_environment()
    return Client()


def login(role, client):
    from django.urls import reverse

    response = client.post(
        reverse("login"),
        {"username": os.environ["GC43_EMAIL"], "password": os.environ["GC43_PASSWORD"]},
    )
    if response.status_code != 302:
        fail(role, f"login returned {response.status_code}, expected 302")
    if client.session.get("mode") == "child":
        fail(role, "fresh login unexpectedly restored child mode")


def role_preflight():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    import django

    django.setup()
    from django.conf import settings

    db = settings.DATABASES["default"]
    print(json.dumps({"role": "preflight", "engine": db["ENGINE"], "db_name": str(db["NAME"])}))


def role_seed():
    """Synthetic principals only; the reading progress itself is never written here."""
    django_ready("seed")
    from django.contrib.auth.hashers import make_password

    from apps.accounts.models import Account, ChildProfile, Reader
    from apps.library.models import Book

    account = Account.objects.create_user(
        os.environ["GC43_EMAIL"], os.environ["GC43_PASSWORD"], display_name="Părinte S43"
    )
    account.pin_hash = make_password(os.environ["GC43_PIN"])
    account.save(update_fields=["pin_hash"])
    Reader.objects.create(kind=Reader.ADULT, account=account)
    child = ChildProfile.objects.create(guardian=account, nickname="Mia S43", age_band="9-11", avatar="fox")
    Reader.objects.create(kind=Reader.CHILD, child=child)
    book = Book.objects.create(
        title="Capra cu trei iezi (S43)",
        author="Sintetic",
        language="ro",
        page_count=BOOK_PAGES,
        age_band="9-11",
        genre="fairy_tale",
        cover_color="#F4A261",
        cover_emoji="fox",
        source_note="synthetic fixture for issue 43",
    )
    write_state(
        "seed",
        {
            "guardian_pk": account.pk,
            "child_public_id": str(child.public_id),
            "book_public_id": str(book.public_id),
        },
    )
    print(json.dumps({"role": "seed", "status": "OK"}))


def role_writer():
    settings = django_ready("writer")
    from django.urls import reverse

    from apps.library.models import ProgressEvent, ShelfEntry

    state = read_state("writer")
    client = test_client()
    login("writer", client)
    entered = client.post(reverse("child_mode_start", args=[state["child_public_id"]]))
    if entered.status_code != 302 or entered["Location"] != reverse("child_home"):
        fail("writer", f"child_mode_start returned {entered.status_code} {getattr(entered, 'Location', None)}")
    if client.session.get("mode") != "child" or client.session.get("active_child") != state["child_public_id"]:
        fail("writer", "session did not enter child mode for the synthetic child")
    added = client.post(reverse("add_to_shelf", args=[state["book_public_id"]]), **HTMX)
    if added.status_code != 204 or added["HX-Trigger"] != "saved":
        fail("writer", f"add_to_shelf returned {added.status_code}")
    entry_public_id = added["HX-Redirect"].rstrip("/").rsplit("/", 1)[-1]
    page = client.get(reverse("shelf_entry", args=[entry_public_id]))
    if page.status_code != 200:
        fail("writer", f"shelf_entry returned {page.status_code}")
    request_id = str(page.context["request_id"])
    saved = client.post(
        reverse("record_progress", args=[entry_public_id]), {"page": PAGE, "request_id": request_id}, **HTMX
    )
    if saved.status_code != 200 or saved["HX-Trigger"] != "saved":
        fail("writer", f"record_progress returned {saved.status_code}")
    if "child/_progress.html" not in {t.name for t in saved.templates}:
        fail("writer", "record_progress did not render the child progress partial")
    # Read-only verification: the write itself happened through the HTTP route above.
    entry = ShelfEntry.objects.select_related("book").get(public_id=entry_public_id)
    events = ProgressEvent.objects.count()
    if (entry.current_page, entry.book.page_count) != (PAGE, BOOK_PAGES) or events != 1:
        fail("writer", f"readback {entry.current_page}/{entry.book.page_count}, events={events}")
    state.update(
        entry_public_id=entry_public_id,
        page_count=entry.book.page_count,
        current_page=entry.current_page,
        progress_events=events,
        writer_session_key_sha256=hashlib.sha256(client.session.session_key.encode()).hexdigest(),
    )
    write_state("writer", state)
    print(
        json.dumps(
            {
                "role": "writer",
                "status": "OK",
                "db_basename": Path(str(settings.DATABASES["default"]["NAME"])).name,
                "current_page": entry.current_page,
                "page_count": entry.book.page_count,
                "progress_events": events,
            }
        )
    )


def role_reader():
    django_ready("reader")
    from django.conf import settings
    from django.urls import reverse

    from apps.accounts.models import ChildProfile
    from apps.core.viewmodels import StatsVM
    from apps.library.models import ProgressEvent, ShelfEntry

    state = read_state("reader")
    db_name = Path(str(settings.DATABASES["default"]["NAME"])).resolve()
    events_before = ProgressEvent.objects.count()
    if events_before != state["progress_events"]:
        fail("reader", f"found {events_before} events, writer recorded {state['progress_events']}")
    client = test_client()
    login("reader", client)
    if hashlib.sha256(client.session.session_key.encode()).hexdigest() == state["writer_session_key_sha256"]:
        fail("reader", "reader session equals the writer session")
    child = ChildProfile.objects.get(public_id=state["child_public_id"])
    if child.guardian_id != state["guardian_pk"] or client.session.get("_auth_user_id") != str(child.guardian_id):
        fail("reader", "child does not belong to the freshly logged-in guardian")
    report = client.get(reverse("child_report", args=[state["child_public_id"]]))
    if report.status_code != 200 or "adult/child_report.html" not in {t.name for t in report.templates}:
        fail("reader", f"child_report returned {report.status_code}")
    if report.context["child"].public_id != child.public_id:
        fail("reader", "child_report shows a different child")
    [shown] = report.context["entries"]
    if (shown.current_page, shown.page_count) != (PAGE, BOOK_PAGES):
        fail("reader", f"child_report shows {shown.current_page}/{shown.page_count}")
    if report.context["stats"] != StatsVM(1, 0, PAGE, PAGE):
        fail("reader", f"child_report stats are {report.context['stats']}")
    dashboard = client.get(reverse("adult_dashboard"))
    if dashboard.status_code != 200:
        fail("reader", f"adult_dashboard returned {dashboard.status_code}")
    [card] = dashboard.context["children"]
    if (
        card["child"].public_id != child.public_id
        or card["current_entry"].current_page != PAGE
        or card["current_entry"].page_count != BOOK_PAGES
    ):
        fail("reader", "adult_dashboard card does not show 35/120")
    events_after = ProgressEvent.objects.count()
    if events_after != events_before:
        fail("reader", f"read-only GET changed the event count: {events_before} -> {events_after}")
    entry = ShelfEntry.objects.select_related("book").get(public_id=state["entry_public_id"])
    if (entry.current_page, entry.book.page_count, entry.status) != (PAGE, BOOK_PAGES, ShelfEntry.READING):
        fail("reader", f"stored entry changed: {entry.current_page}/{entry.book.page_count} {entry.status}")
    print(
        json.dumps(
            {
                "role": "reader",
                "status": "OK",
                "db_basename": db_name.name,
                "same_db_file": db_name == Path(os.environ["GC43_DB"]).resolve(),
                "outside_repo": REPO_ROOT not in db_name.parents,
                "current_page": shown.current_page,
                "page_count": shown.page_count,
                "progress_events": events_after,
                "progress_events_unchanged": events_after == events_before,
                "session_keys_differ": True,
            }
        )
    )


def build_child_env():
    # Child scripts are launched from scripts/, so the repo root must be on sys.path
    # for the config/ and apps/ packages to be importable.
    pythonpath = str(REPO_ROOT)
    if os.environ.get("PYTHONPATH"):
        pythonpath += os.pathsep + os.environ["PYTHONPATH"]
    env = {key: value for key, value in os.environ.items() if key not in SCRUBBED}
    env.update(
        {
            "DJANGO_SETTINGS_MODULE": "config.settings.dev",
            "DATABASE_URL": "",  # replaced below once the temp path exists
            "PYTHONPATH": pythonpath,
            "GC43_EMAIL": f"synth43-{secrets.token_hex(6)}@example.invalid",
            "GC43_PASSWORD": secrets.token_urlsafe(18),
            "GC43_PIN": str(secrets.randbelow(9000) + 1000),
            "PYTHONUTF8": "1",
        }
    )
    return env


def run(role, env):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--role", role], cwd=REPO_ROOT, env=env,
        capture_output=True, text=True, encoding="utf-8",
    )


def last_json(output):
    return json.loads(output.strip().splitlines()[-1])


def orchestrate():
    with tempfile.TemporaryDirectory(prefix="gc43-synth-") as tmp:
        tmp_dir = Path(tmp).resolve()
        db_path = tmp_dir / DB_FILE
        if REPO_ROOT in tmp_dir.parents or REPO_ROOT in db_path.parents:
            fail("orchestrator", "temp dir is inside the repository")
        env = build_child_env()
        env["GC43_TMP"] = str(tmp_dir)
        env["GC43_DB"] = str(db_path)
        env["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"

        preflight = run("preflight", env)
        if preflight.returncode != 0:
            fail("orchestrator", f"preflight failed before any migration:\n{preflight.stderr}")
        pre = last_json(preflight.stdout)
        if pre["engine"] != "django.db.backends.sqlite3" or Path(pre["db_name"]).resolve() != db_path.resolve():
            fail("orchestrator", f"effective settings do not point at the temp DB: {pre}")

        migrate = subprocess.run(
            [sys.executable, "manage.py", "migrate", "--noinput"], cwd=REPO_ROOT, env=env,
            capture_output=True, text=True, encoding="utf-8",
        )
        if migrate.returncode != 0:
            fail("orchestrator", f"migrate failed (exit {migrate.returncode}):\n{migrate.stderr}")

        for role in ("seed", "writer", "reader"):
            result = run(role, env)
            if result.returncode != 0:
                fail("orchestrator", f"{role} failed (exit {result.returncode}):\n{result.stdout}\n{result.stderr}")
            print(result.stdout.strip())
    # Leaving the with-block removes the temp DB and state file; nothing outside is touched.
    print(json.dumps({"role": "orchestrator", "status": "cleanup", "temp_db_removed": True}))


ROLES = {
    "preflight": role_preflight,
    "seed": role_seed,
    "writer": role_writer,
    "reader": role_reader,
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Issue #43 synthetic cross-process persistence proof")
    parser.add_argument("--role", choices=sorted(ROLES), help="internal: run a single child role")
    args = parser.parse_args()
    if args.role:
        ROLES[args.role]()
    else:
        orchestrate()
