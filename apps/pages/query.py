from django.db.models import Q
from django.db.models.query import QuerySet
from django.utils.timezone import now


class PageQuerySet(QuerySet):
    def published(self):
        return self.filter(is_active=True).filter(Q(publication_date__lte=now()) | Q(publication_date__isnull=True))
