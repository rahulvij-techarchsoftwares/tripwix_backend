from django.db.models.query import QuerySet


class ComponentFormQuerySet(QuerySet):
    def published(self):
        return self.filter(is_active=True)
