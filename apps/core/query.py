from django.db.models import Func, TextField, Value
from django.db.models.query import QuerySet
from django.utils import timezone


class FakeQuerySet:
    def __init__(self, list_of_model_items):
        self.list_of_model_items = list_of_model_items
        self._prefetch_related_lookups = ()
        self._prefetch_done = False

    def iterator(self):
        return self.list_of_model_items


class UndeletedQuerySet(QuerySet):
    def soft_delete(self, **kwargs):
        return self.update(delete_ts=timezone.now(), **kwargs)


class ExtractLastWord(Func):
    function = 'REGEXP_REPLACE'
    template = "%(function)s(%(expressions)s)"

    def __init__(self, expression):
        super().__init__(
            expression,
            Value(r'^.*\s'),
            Value(''),
            Value('g'),
            output_field=TextField(),
        )


class ExtractNumber(Func):
    function = 'REGEXP_REPLACE'
    template = "%(function)s(%(expressions)s)"

    def __init__(self, expression):
        super().__init__(
            expression,
            Value(r'[^0-9]'),
            Value(''),
            Value('g'),
            output_field=TextField(),
        )
