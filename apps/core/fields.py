from django import forms
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.forms import JSONField
from django.utils.translation import gettext_lazy as _
from modeltrans.fields import TranslationField as ModelTransField

from apps.core import widgets as core_widgets


class TranslationField(ModelTransField):
    pass


class AppField(forms.JSONField):
    def __init__(
        self,
        *args,
        app_model=None,
        content_type_field=None,
        object_field=None,
        ignore_list=[],
        is_multiple=False,
        **kwargs
    ):
        super(AppField, self).__init__(max_length=250, **kwargs)
        self.app_model = app_model

        widget_class_attr = 'js-app-input'
        if 'widget' in kwargs:
            widget_class_attr = kwargs['widget'].attrs.get('class', '') + ' js-app-input'

        self.widget = core_widgets.AppWidget(
            attrs={'class': widget_class_attr},
            content_type_field=content_type_field,
            object_field=object_field,
            app_model=app_model,
            ignore_list=ignore_list,
            is_multiple=is_multiple,
        )

    def set_initial(self, content_type_id, object_pk):
        self.initial = {
            'content_type_id': content_type_id,
            'object_pk': object_pk,
        }

    def validate(self, value):
        if value in self.empty_values and self.required:
            raise ValidationError(self.error_messages["required"], code="required")

        if value:
            data_dict = value or {}

            if not data_dict.get('content_type_id') and self.required:
                raise ValidationError(self.error_messages["required"], code="required")

            if not data_dict.get('object_pk') and self.required:
                raise ValidationError(self.error_messages["required"], code="required")

            # validate that object(s) exists.
            object_exists = False
            if data_dict.get('content_type_id') and data_dict.get('object_pk'):
                if isinstance(data_dict.get('object_pk'), list):
                    object_ids = data_dict.get('object_pk')
                else:
                    object_ids = [
                        data_dict.get('object_pk'),
                    ]
                try:
                    content_type = ContentType.objects.get(id=data_dict.get('content_type_id'))
                    if self.app_model and self.app_model.pk != content_type.pk:
                        object_exists = False
                    else:
                        object_exists = content_type.get_all_objects_for_this_type(id__in=object_ids).exists()
                except Exception:
                    pass

            if self.required and not object_exists:
                raise ValidationError(self.error_messages["required"], code="required")
