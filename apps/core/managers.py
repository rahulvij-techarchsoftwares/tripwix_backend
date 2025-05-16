from django.db import models

from apps.core.query import UndeletedQuerySet


class UndeletedManager(models.Manager):
    def get_queryset(self):
        return UndeletedQuerySet(model=self.model, using=self._db, hints=self._hints).filter(deleted_at__isnull=True)
