from django.db import models
from django.db.models import Q
from django.utils import timezone


class LocationManager(models.Manager):
    def with_properties_published(self):
        return (
            self.get_queryset()
            .filter(property__isnull=False, property__is_active=True)
            .filter(
                Q(property__publication_date__lte=timezone.now()) | Q(property__publication_date__isnull=True),
                Q(property__publication_end_date__gt=timezone.now()) | Q(property__publication_end_date__isnull=True),
            )
            .distinct()
        )


class SubLocationManager(models.Manager):

    def with_properties_published(self):
        return (
            self.get_queryset()
            .filter(property__isnull=False, property__is_active=True)
            .filter(
                Q(property__publication_date__lte=timezone.now()) | Q(property__publication_date__isnull=True),
                Q(property__publication_end_date__gt=timezone.now()) | Q(property__publication_end_date__isnull=True),
            )
            .distinct()
        )
