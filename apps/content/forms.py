import json

from django import forms
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.forms import CharField
from django.utils.translation import gettext_lazy as _

from apps.core import fields as core_fields
from apps.core import widgets as core_widgets

from .models import Content


class ContentAdminForm(forms.ModelForm):
    object_id = forms.CharField(max_length=100, required=False)
    content_object = core_fields.AppField(
        content_type_field='app_model',
        object_field='object_id',
        ignore_list=[
            Content,
        ],
        required=False,
    )

    class Meta:
        model = Content
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super(ContentAdminForm, self).__init__(*args, **kwargs)
        instance = kwargs.get('instance')

        if instance and instance.pk and instance.content_type == Content.Types.APP:
            self.fields['content_object'].required = True
            self.fields['content_object'].set_initial(
                instance.app_model.id if instance.app_model else "", instance.object_id
            )
            self.fields['app_model'].widget = forms.HiddenInput()
            self.fields['object_id'].widget = forms.HiddenInput()
