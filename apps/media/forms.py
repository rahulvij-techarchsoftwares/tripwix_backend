import six
from django import forms
from django.db.models.query import QuerySet
from django.utils.encoding import force_str

from .widgets import MediaPhotoFkWidget, MediaPhotoWidget


class MediaPhotoChoiceField(forms.ModelMultipleChoiceField):
    widget = MediaPhotoWidget
    can_select = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.widget.queryset = self.queryset
        self.widget.to = self.queryset.model
        self.widget.can_select = self.can_select


class MediaPhotoFkField(forms.ModelChoiceField):
    widget = MediaPhotoFkWidget
    can_select = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.widget.queryset = self.queryset
        self.widget.to = self.queryset.model
        self.widget.can_select = self.can_select

    def clean(self, value):
        from apps.media.fields import SortedMultipleChoiceField

        queryset = super().clean(value)
        if value is None or not isinstance(queryset, QuerySet):
            return queryset

        object_list = dict((str(key), value) for key, value in six.iteritems(queryset.in_bulk(value)))
        return [object_list[str(pk)] for pk in value]

    def _has_changed(self, initial, data):
        if initial is None:
            initial = []
        if data is None:
            data = []
        if len(initial) != len(data):
            return True
        initial_set = [force_str(value) for value in self.prepare_value(initial)]
        data_set = [force_str(value) for value in data]
        return data_set != initial_set
