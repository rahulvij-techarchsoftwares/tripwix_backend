import copy
import datetime
import json
import posixpath
from decimal import Decimal

from django import forms
from django.contrib.admin import widgets as admin_widgets
from django.core import serializers
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile
from django.core.files.utils import validate_file_name
from django.db import models
from django.db.models.fields.files import FieldFile
from django.db.models.query import QuerySet
from django_admin_kubi.widgets import TinyMceEditorWidget
from phonenumber_field.formfields import PhoneNumberField
from phonenumber_field.phonenumber import PhoneNumber

from apps.core import fields as core_fields
from apps.core import widgets as core_widgets
from apps.core.utils import get_default_lang, get_translation_fields
from apps.core.widgets import PhoneNumberWidget
from apps.media.forms import MediaPhotoChoiceField, MediaPhotoFkField
from apps.media.models import MediaPhoto

from . import choices, widgets
from .utils import get_attrs_by_unit, get_component_fields_gen, get_model_object_by_pk


class CollectionAdminForm(forms.ModelForm):
    FORM_FIELD_AND_WIDGET_MAP = {
        choices.FIELD_TEXT: (forms.CharField, None),
        choices.FIELD_BOOL: (forms.BooleanField, None),
        choices.FIELD_OPTION: (forms.ModelChoiceField, core_widgets.SelectizeWidget),
        choices.FIELD_DATE: (forms.DateField, admin_widgets.AdminDateWidget),
        choices.FIELD_TIME: (forms.TimeField, admin_widgets.AdminTimeWidget),
        choices.FIELD_DATETIME: (forms.SplitDateTimeField, admin_widgets.AdminSplitDateTime),
        choices.FIELD_NUMBER: (forms.DecimalField, None),
        choices.FIELD_INTEGER: (forms.IntegerField, None),
        choices.FIELD_COLOR: (forms.CharField, core_widgets.ColorWidget),
        choices.FIELD_APP: (core_fields.AppField, None),
        choices.FIELD_CTA: (forms.JSONField, core_widgets.CTAWidget),
        choices.FIELD_DESCRIPTION: (forms.CharField, core_widgets.RichTextEditorWidget),
        choices.FIELD_JSON_FIELD: (forms.JSONField, None),
        choices.FIELD_IMAGE: (MediaPhotoFkField, None),
        choices.FIELD_EMAIL: (forms.EmailField, None),
        choices.FIELD_PHONE: (PhoneNumberField, PhoneNumberWidget),
        choices.FIELD_FILE: (forms.FileField, admin_widgets.AdminFileWidget),
    }

    def get_field_and_widget(self, component_field, is_multiple=False):
        FormField, FieldWidget = self.FORM_FIELD_AND_WIDGET_MAP.get(component_field.field_type, (forms.CharField, None))

        field_options = {}
        widget_options = {}
        widget_attrs = {}
        if component_field.field_type == choices.FIELD_OPTION:
            field_options = dict(queryset=component_field.options)
            if is_multiple:
                FormField, FieldWidget = (forms.ModelMultipleChoiceField, core_widgets.SelectizeMultipleWidget)
        elif component_field.field_type == choices.FIELD_APP:
            if component_field.app_model:
                field_options = dict(app_model=component_field.app_model)
            field_options['is_multiple'] = is_multiple
        elif component_field.field_type == choices.FIELD_DESCRIPTION:
            widget_attrs = {'class': 'vLargeTextField'}
        elif component_field.field_type == choices.FIELD_IMAGE:
            field_options = dict(queryset=MediaPhoto.objects.all())
            if is_multiple:
                FormField, FieldWidget = (MediaPhotoChoiceField, None)

        if component_field.unit:
            widget_attrs.update(get_attrs_by_unit(component_field.unit))

        if widget_attrs:
            widget_options.update({'attrs': widget_attrs})

        return FormField, FieldWidget, field_options, widget_options

    def format_field_value(self, value, field, is_multiple):
        # this enables is_multiple swapability on fields
        if field.field_type == choices.FIELD_IMAGE:
            if is_multiple and not isinstance(value, (list, tuple)):
                value = (
                    [
                        value,
                    ]
                    if value
                    else []
                )
            elif not is_multiple and isinstance(value, (list, tuple)):
                value = value[0] if value else None

        elif field.field_type == choices.FIELD_DATETIME:
            return forms.DateTimeField().to_python(value=value)
        elif field.field_type == choices.FIELD_FILE:
            return FieldFile(None, models.FileField(), value)
        return value

    def handle_list_value(self, list_items) -> list:
        return [self.handle_field_value(v) for v in list_items]

    def handle_upload_value(self, value):
        dirname = datetime.datetime.now().strftime(str(self.upload_to))
        filename = posixpath.join(dirname, value.name)
        filename = validate_file_name(filename, allow_relative_path=True)
        filename = self.storage.generate_filename(filename)
        return self.storage.save(filename, value.file, max_length=100)

    def handle_field_value(self, value):
        if isinstance(value, list):
            return self.handle_list_value(value)
        elif isinstance(value, QuerySet):
            return list(value.values_list('id', flat=True))
        elif isinstance(value, models.Model):
            return value.pk if isinstance(value.pk, int) else str(value.pk)
        elif isinstance(value, Decimal):
            return '%.2f' % value
        elif isinstance(value, datetime.time):
            return value.isoformat()
        elif isinstance(value, datetime.date):
            return value.isoformat()
        elif isinstance(value, datetime.datetime):
            return value.isoformat()
        elif isinstance(value, PhoneNumber):
            return str(value)
        elif isinstance(value, UploadedFile):
            return self.handle_upload_value(value)
        elif isinstance(value, FieldFile):
            return value.name
        return value

    def get_field_value(self, cleaned_data, field_name):
        value = cleaned_data[field_name]
        if value is None:
            return None
        return self.handle_field_value(value)

    def custom_fields_to_data_json(self, cleaned_data):
        fields_to_json = {}
        default_language = get_default_lang()

        for field, field_name, component_field, _component, _block_pk in get_component_fields_gen(self.instance):
            if component_field.is_translatable:
                fallback_value = None
                for trans_field in get_translation_fields(field_name):
                    lang = trans_field.split("_")[-1]
                    fields_to_json[trans_field] = self.get_field_value(cleaned_data, trans_field)
                    if lang == default_language:
                        fallback_value = fields_to_json[trans_field]
                fields_to_json[field_name] = fallback_value
            else:
                fields_to_json[field_name] = self.get_field_value(cleaned_data, field_name)

        return fields_to_json

    def __init__(self, *args, **kwargs):
        super(CollectionAdminForm, self).__init__(*args, **kwargs)

        if not self.instance.pk:
            return None

        self.storage = default_storage
        instance_name = self.instance.__class__.__name__.lower()
        self.upload_to = f"f/{instance_name}"
        default_language = get_default_lang()

        for field, field_name, component_field, _component, _block_pk in get_component_fields_gen(self.instance):
            field_label = component_field.name
            is_required = component_field.is_required
            field_type = field.field_type

            default_field_options = {'label': field_label, 'required': is_required}

            FormField, FieldWidget, field_options, widget_options = self.get_field_and_widget(
                field, is_multiple=component_field.is_multiple
            )
            Widget = FieldWidget or FormField.widget

            if component_field.is_translatable:
                for trans_field in get_translation_fields(field_name):
                    lang = trans_field.split("_")[-1]
                    attrs = {
                        'class': 'mt %s %s'
                        % ("mt-field-%s-%s" % (field_name, lang), "mt-default" if lang == default_language else "")
                    }
                    trans_field_options = default_field_options.copy()
                    trans_field_options['label'] = f"{default_field_options['label']} [{lang}]"
                    trans_field_options['required'] = lang == default_language and is_required
                    trans_widget_options = copy.deepcopy(widget_options)
                    if 'attrs' in trans_widget_options and 'class' in trans_widget_options['attrs']:
                        trans_widget_options['attrs'][
                            'class'
                        ] = f"{trans_widget_options['attrs']['class']} {attrs['class']}"
                    elif 'attrs' in trans_widget_options:
                        trans_widget_options['attrs'].update(attrs)
                    else:
                        trans_widget_options['attrs'] = attrs
                    self.fields[trans_field] = FormField(
                        **trans_field_options, **field_options, widget=Widget(**trans_widget_options)
                    )
            else:
                self.fields[field_name] = FormField(
                    **default_field_options, **field_options, widget=Widget(**widget_options)
                )

            # get initial data for fields
            if self.instance and self.instance.fields_data_json:
                if component_field.is_translatable:
                    for index, trans_field in enumerate(get_translation_fields(field_name)):
                        original_field_value = self.instance.fields_data_json.get(field_name) if index == 0 else None
                        field_value = self.instance.fields_data_json.get(trans_field, original_field_value)
                        self.initial[trans_field] = self.format_field_value(
                            field_value, field, component_field.is_multiple
                        )
                else:
                    field_value = self.instance.fields_data_json.get(field_name)
                    self.initial[field_name] = self.format_field_value(field_value, field, component_field.is_multiple)

    def save(self, *args, **kwargs):
        obj = super(CollectionAdminForm, self).save(*args, **kwargs)
        if obj.pk:
            data_json = self.custom_fields_to_data_json(self.cleaned_data)
            original_data = obj.fields_data_json.copy() if obj.fields_data_json else {}
            obj.fields_data_json = {**original_data, **data_json}
        return obj
