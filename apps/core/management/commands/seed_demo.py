"""Idempotent synthetic demo data. All people are fictional, all emails are @demo.local, books are metadata only."""

import os
from datetime import datetime, timezone

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import Account, ChildProfile, Reader
from apps.club.models import Achievement, ClubActivity
from apps.library.models import Book

DEMO_DOMAIN = "@demo.local"

ACCOUNTS = [
    # email, display name, is_staff
    ("admin@demo.local", "Admin Club (demo)", True),
    ("parinte1@demo.local", "Părinte Demo 1", False),  # guardian of Mia and Alex
    ("parinte2@demo.local", "Părinte Demo 2", False),  # guardian with no children (foreign-access checks)
    ("cititor@demo.local", "Cititor Demo", False),  # adult self-reader without children (US4)
]

CHILDREN = [
    # guardian email, nickname, age band, avatar
    ("parinte1@demo.local", "Mia", "9-11", "fox"),
    ("parinte1@demo.local", "Alex", "7-8", "owl"),
]

_PD = "Metadate sintetice pentru demo; operă în domeniul public (autor decedat înainte de 1955). Număr de pagini ilustrativ, nu o ediție anume."
BOOKS = [
    # title, author, pages, age band, genre, colour, emoji
    ("Capra cu trei iezi", "Ion Creangă", 120, "7-8", "fairy_tale", "#F4A261", "🐐"),
    ("Punguța cu doi bani", "Ion Creangă", 40, "7-8", "fairy_tale", "#E9C46A", "🐓"),
    ("Ursul păcălit de vulpe", "Ion Creangă", 32, "7-8", "animals", "#E76F51", "🦊"),
    ("Povestea lui Harap-Alb", "Ion Creangă", 96, "12-15", "fairy_tale", "#264653", "🐎"),
    ("Amintiri din copilărie", "Ion Creangă", 180, "12-15", "story", "#2A9D8F", "🏡"),
    ("Făt-Frumos din lacrimă", "Mihai Eminescu", 64, "9-11", "fairy_tale", "#8AB17D", "💧"),
    ("Prâslea cel voinic și merele de aur", "Petre Ispirescu", 48, "9-11", "fairy_tale", "#F6BD60", "🍎"),
    ("Tinerețe fără bătrânețe și viață fără de moarte", "Petre Ispirescu", 56, "12-15", "fairy_tale", "#84A59D", "🏰"),
    ("Greuceanu", "Petre Ispirescu", 60, "9-11", "adventure", "#F28482", "⚔️"),
    ("Zâna Zorilor", "Ioan Slavici", 72, "9-11", "fairy_tale", "#A2D2FF", "🌅"),
    ("D-l Goe…", "Ion Luca Caragiale", 16, "9-11", "humor", "#CDB4DB", "🎩"),
    ("Din lumea celor care nu cuvântă", "Emil Gârleanu", 110, "9-11", "animals", "#B5E48C", "🐞"),
]

ACHIEVEMENTS = [
    # code, title, description, rule, threshold, members_only, icon
    ("first-book", "Prima carte", "Ai terminat prima carte.", "books_finished_gte", 1, False, "first-book.svg"),
    ("pages-100", "100 de pagini", "Ai citit 100 de pagini.", "pages_total_gte", 100, False, "pages-100.svg"),
    ("club-reader", "Cititor de Club", "Prima carte terminată ca membru al clubului.", "books_finished_gte", 1, True,
     "club-reader.svg"),
]

ACTIVITIES = [
    # title, description, place, starts_at (UTC)
    ("Seară de povești de toamnă", "Citim și discutăm împreună o poveste.", "Online",
     datetime(2026, 11, 15, 16, 0, tzinfo=timezone.utc)),
    ("Atelier: desenăm personajul preferat", "Fiecare copil aduce cartea pe care o citește acum.", "Sala clubului",
     datetime(2026, 11, 29, 10, 0, tzinfo=timezone.utc)),
]


class Command(BaseCommand):
    help = "Create or update synthetic demo data (idempotent). Credentials come from DEMO_PASSWORD / DEMO_PIN."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete demo accounts (and their children, shelves, progress, grants) before seeding. "
            "Refuses if the database holds any non-demo account.",
        )

    def handle(self, *args, reset=False, **options):
        password = os.environ.get("DEMO_PASSWORD") or None
        pin = os.environ.get("DEMO_PIN") or None
        if pin and not (pin.isdigit() and 4 <= len(pin) <= 6):
            raise CommandError("DEMO_PIN must be 4–6 digits.")

        with transaction.atomic():
            if reset:
                foreign = Account.objects.exclude(email__endswith=DEMO_DOMAIN).count()
                if foreign:
                    raise CommandError(f"--reset refused: {foreign} non-demo account(s) present; this is not a demo-only database.")
                Account.objects.filter(email__endswith=DEMO_DOMAIN).delete()
            counts = self._seed(password, pin)

        self.stdout.write(self.style.SUCCESS("seed_demo: " + ", ".join(f"{k}={v}" for k, v in counts.items())))
        if not password:
            self.stdout.write("DEMO_PASSWORD not set: demo accounts have unusable passwords.")
        if not pin:
            self.stdout.write("DEMO_PIN not set: guardians have no PIN yet.")

    def _seed(self, password, pin):
        accounts = {}
        for email, name, is_staff in ACCOUNTS:
            account, _ = Account.objects.get_or_create(email=email, defaults={"display_name": name})
            account.display_name = name
            account.is_staff = account.is_superuser = is_staff
            account.set_password(password)  # None → unusable
            if not is_staff:
                account.pin_hash = make_password(pin) if pin else None
            account.save()
            accounts[email] = account
            if not is_staff:
                Reader.objects.get_or_create(kind=Reader.ADULT, account=account)

        for guardian_email, nickname, age_band, avatar in CHILDREN:
            child, _ = ChildProfile.objects.update_or_create(
                guardian=accounts[guardian_email], nickname=nickname,
                defaults={"age_band": age_band, "avatar": avatar},
            )
            Reader.objects.get_or_create(kind=Reader.CHILD, child=child)

        for title, author, pages, age_band, genre, colour, emoji in BOOKS:
            Book.objects.update_or_create(
                title=title, author=author,
                defaults={
                    "page_count": pages, "age_band": age_band, "genre": genre, "language": "ro",
                    "cover_color": colour, "cover_emoji": emoji, "source_note": _PD, "is_active": True,
                },
            )

        for code, title, description, rule, threshold, members_only, icon in ACHIEVEMENTS:
            Achievement.objects.update_or_create(
                code=code,
                defaults={"title": title, "description": description, "rule": rule, "threshold": threshold,
                          "members_only": members_only, "icon": icon},
            )

        for title, description, place, starts_at in ACTIVITIES:
            ClubActivity.objects.update_or_create(
                title=title, defaults={"description": description, "place": place, "starts_at": starts_at,
                                       "is_published": True},
            )

        # Totals actually in the database, so a second run visibly reports the same numbers.
        return {
            "demo_accounts": Account.objects.filter(email__endswith=DEMO_DOMAIN).count(),
            "children": ChildProfile.objects.count(),
            "readers": Reader.objects.count(),
            "books": Book.objects.count(),
            "achievements": Achievement.objects.count(),
            "activities": ClubActivity.objects.count(),
        }
