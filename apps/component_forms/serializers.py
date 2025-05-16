from collections.abc import Mapping

from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework import serializers, validators
from rest_framework.utils import html

from apps.components import choices
from apps.components.serializers import FieldSerializer
from apps.core.serializers import ModelTypeSerializer, SeoSerializerMixin, SlugSerializerMixin

from .models import ComponentForm, ComponentFormFields


class ComponentFormFieldSerializer(ModelTypeSerializer):
    field = FieldSerializer()

    class Meta:
        model = ComponentFormFields
        fields = ('name', 'slug', 'is_required', 'is_multiple', 'field', *ModelTypeSerializer.Meta.fields)


class SimpleComponentFormSerializer(ModelTypeSerializer):
    class Meta:
        model = ComponentForm
        fields = ('title', 'slug', *ModelTypeSerializer.Meta.fields)


class ComponentFormSerializer(ModelTypeSerializer):
    schema = serializers.SerializerMethodField()

    def get_schema(self, obj):
        return ComponentFormFieldSerializer(obj.form_fields.all().select_related('field'), many=True).data

    class Meta:
        model = ComponentForm
        fields = ('title', 'slug', 'schema', *ModelTypeSerializer.Meta.fields)


class AppField(serializers.CharField):
    def __init__(self, *args, **kwargs):
        self.app_model = kwargs.pop('app_model', None)
        self.allow_empty = kwargs.pop('allow_empty', True)
        super(AppField, self).__init__(*args, **kwargs)

    def run_validate(self, value):
        if self.app_model:
            if not self.app_model.get_all_objects_for_this_type(id=value).exists():
                raise serializers.ValidationError(f"{value} is not a valid choice.")
        return value

    def to_representation(self, value):
        return value

    def to_internal_value(self, data):
        return self.run_validate(data)


class MultipleAppField(AppField):
    def run_validate(self, value):
        if self.app_model:
            valid_pks = self.app_model.get_all_objects_for_this_type(id__in=value).values_list('pk', flat=True)
            missing_pks = [v for v in value if v not in valid_pks]
            if missing_pks:
                raise serializers.ValidationError(f"{missing_pks} is not a valid choice.")
            if len(valid_pks) != len(value):
                raise serializers.ValidationError("No duplicate references allowed.")
        return value

    def to_internal_value(self, data):
        if html.is_html_input(data):
            data = html.parse_html_list(data, default=[])
        if isinstance(data, (str, Mapping)) or not hasattr(data, '__iter__'):
            self.fail('not_a_list', input_type=type(data).__name__)
        if not self.allow_empty and len(data) == 0:
            self.fail('empty')
        return self.run_validate(data)


class ComponentFormDataSerializer(serializers.Serializer):
    FORM_FIELD_MAP = {
        choices.FIELD_TEXT: serializers.CharField,
        choices.FIELD_BOOL: serializers.BooleanField,
        choices.FIELD_OPTION: serializers.ChoiceField,
        choices.FIELD_DATE: serializers.DateField,
        choices.FIELD_TIME: serializers.TimeField,
        choices.FIELD_DATETIME: serializers.DateTimeField,
        choices.FIELD_NUMBER: serializers.DecimalField,
        choices.FIELD_INTEGER: serializers.IntegerField,
        choices.FIELD_COLOR: serializers.CharField,
        choices.FIELD_APP: AppField,
        choices.FIELD_CTA: serializers.JSONField,
        choices.FIELD_DESCRIPTION: serializers.CharField,
        choices.FIELD_JSON_FIELD: serializers.JSONField,
        choices.FIELD_IMAGE: serializers.ImageField,
        choices.FIELD_EMAIL: serializers.EmailField,
        choices.FIELD_PHONE: PhoneNumberField,
        choices.FIELD_FILE: serializers.FileField,
    }

    def get_field(self, component_field, is_multiple=False):
        FormField = self.FORM_FIELD_MAP.get(component_field.field_type, serializers.JSONField)
        field_options = {}

        if component_field.field_type == choices.FIELD_OPTION:
            field_options = dict(choices=[(o.slug, str(o)) for o in component_field.options.all()])

        elif component_field.field_type == choices.FIELD_APP:
            if component_field.app_model:
                field_options = dict(app_model=component_field.app_model)

        elif component_field.field_type == choices.FIELD_NUMBER:
            field_options = dict(max_digits=12, decimal_places=2)

        return FormField, field_options

    def __init__(self, *args, **kwargs):
        component_form = kwargs.pop('component_form')
        super(ComponentFormDataSerializer, self).__init__(*args, **kwargs)

        if not component_form.pk:
            return None

        for component_form_field in component_form.form_fields.all().select_related('field'):
            FormField, field_options = self.get_field(
                component_form_field.field, is_multiple=component_form_field.is_multiple
            )

            default_field_options = {'label': component_form_field.name, 'required': component_form_field.is_required}

            if component_form_field.is_multiple and component_form_field.field.field_type == choices.FIELD_OPTION:
                self.fields[component_form_field.slug] = serializers.MultipleChoiceField(
                    **default_field_options, **field_options
                )
            elif component_form_field.is_multiple and component_form_field.field.field_type == choices.FIELD_APP:
                self.fields[component_form_field.slug] = MultipleAppField(**default_field_options, **field_options)
            elif component_form_field.is_multiple:
                self.fields[component_form_field.slug] = serializers.ListField(
                    **default_field_options, child=FormField(**field_options)
                )
            else:
                self.fields[component_form_field.slug] = FormField(**default_field_options, **field_options)
