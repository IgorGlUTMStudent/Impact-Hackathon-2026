"""Reader statistics derived solely from committed shelf entries and events."""

from datetime import timedelta

from django.db.models import Count, F, IntegerField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.core.viewmodels import StatsVM
from apps.library.models import ProgressEvent, ShelfEntry


def reader_stats(reader):
    now = timezone.now()
    shelf = ShelfEntry.objects.filter(reader=reader).aggregate(
        books_on_shelf=Count("pk"),
        books_finished=Count("pk", filter=Q(status=ShelfEntry.FINISHED)),
        pages_total=Coalesce(Sum("current_page"), Value(0)),
    )
    recent = ProgressEvent.objects.filter(
        reader=reader, created_at__gte=now - timedelta(days=7), created_at__lte=now,
        to_page__gt=F("from_page"),
    ).aggregate(pages=Coalesce(Sum(F("to_page") - F("from_page"), output_field=IntegerField()), Value(0)))
    return StatsVM(**shelf, pages_7d=recent["pages"])
