import six
from django import forms
from django.db import models
from django.db.models.fields.related import ManyToManyField
from django.db.models.query import QuerySet
from django.utils.encoding import force_str

from .forms import MediaPhotoFkField
from .widgets import MediaPhotoWidget, SortedCheckboxSelectMultiple


class SortedMultipleChoiceField(forms.ModelMultipleChoiceField):
    widget = SortedCheckboxSelectMultiple

    def clean(self, value):
        queryset = super().clean(value)
        if value is None or not isinstance(queryset, QuerySet):
            return queryset

        # GIVE NEW ORDER
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


class MediaPhotoChoiceField(SortedMultipleChoiceField):
    widget = MediaPhotoWidget
    can_select = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.widget.queryset = self.queryset
        self.widget.to = self.queryset.model
        self.widget.can_select = self.can_select


class MediaPhotoForeignKey(models.ForeignKey):
    def __init__(self, to=None, can_select=True, **kwargs):
        from .models import MediaPhoto

        if not to:
            to = MediaPhoto

        self.in_relation_to = to
        self.can_select = can_select
        super().__init__(to, null=True, blank=True, on_delete=models.SET_NULL)
        self.help_text = ""

    def formfield(self, **kwargs):
        defaults = {}
        defaults['form_class'] = MediaPhotoFkField
        defaults['form_class'].to = self.in_relation_to
        defaults['form_class'].can_select = self.can_select
        defaults.update(kwargs)
        return super().formfield(**defaults)


class MediaPhotoField(ManyToManyField):
    def __init__(self, to=None, can_select=True, **kwargs):
        from .models import MediaPhoto

        if not to:
            to = MediaPhoto

        self.in_relation_to = to
        self.can_select = can_select
        super(MediaPhotoField, self).__init__(to, **kwargs)
        self.help_text = ""

    def formfield(self, **kwargs):
        defaults = {}
        defaults['form_class'] = MediaPhotoChoiceField
        defaults['form_class'].to = self.in_relation_to
        defaults['form_class'].can_select = self.can_select
        defaults.update(kwargs)
        return super().formfield(**defaults)
