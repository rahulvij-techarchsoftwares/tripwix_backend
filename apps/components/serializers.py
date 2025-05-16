import json

from django.contrib.contenttypes.models import ContentType
from django.core.files.storage import default_storage
from django.utils import translation
from django.utils.functional import cached_property
from rest_framework import serializers

from apps.components import choices
from apps.components.models import CollectionType, Component, ComponentField, ComponentFieldOption
from apps.components.utils import get_component_fields_gen
from apps.core.serializers import ModelTypeSerializer, SeoSerializerMixin, SlugSerializerMixin
from apps.core.utils import build_localized_fieldname, get_default_lang, get_translation_fields
from apps.media.models import MediaPhoto


class FieldSerializer(ModelTypeSerializer):
    class Meta:
        model = ComponentField
        fields = ('name', 'field_type', 'unit', *ModelTypeSerializer.Meta.fields)


class CollectionTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CollectionType
        fields = ('id', 'name', 'slug')


class ComponentFieldOptionSerializer(ModelTypeSerializer):
    class Meta:
        model = ComponentFieldOption
        fields = ('name', 'slug', *ModelTypeSerializer.Meta.fields)


class ComponentFieldSerializer(ModelTypeSerializer):
    name = serializers.SerializerMethodField()
    value = serializers.SerializerMethodField()

    def _get_value(self, data, value):
        if not data or not value:
            return None
        return data.get(value) or data.get(str(value))

    def get_name(self, obj):
        return self.context['name']

    def get_value(self, obj):
        value = self.context['value']

        if value is None:
            return None

        current_lang = self.context['current_lang']
        prefetched_data = self.context['prefetched']

        def get_data_for_model_class(model_class, value):
            if isinstance(value, list):
                result = [get_data_for_model_class(model_class, v) for v in value]
                return [r for r in result if r is not None]
            model_obj = self._get_value(prefetched_data[model_class], value)
            if model_obj and hasattr(model_class, 'get_model_serializer'):
                app_model_serializer = model_class.get_model_serializer(model_obj)
                return app_model_serializer(model_obj).data
            elif not model_obj:
                return None
            return value

        if obj.field_type == choices.FIELD_OPTION:
            if isinstance(value, list):
                options = [v for k, v in prefetched_data[ComponentFieldOption].items() if k in value]
                return ComponentFieldOptionSerializer(options, many=True).data if options else None
            else:
                option = self._get_value(prefetched_data[ComponentFieldOption], value)
                return ComponentFieldOptionSerializer(option).data if option else None

        elif obj.field_type == choices.FIELD_IMAGE:
            return get_data_for_model_class(MediaPhoto, value)

        elif obj.field_type == choices.FIELD_CTA:
            model_class = value.pop('model_class', None)
            object_pk = value.pop('object_pk', None)
            content_type_id = value.pop('content_type_id', None)
            is_internal = value.pop('internal', False)
            value['object'] = None
            if is_internal and model_class and object_pk:
                value['object'] = get_data_for_model_class(model_class, object_pk)
                value['url'] = None

            return value

        elif obj.field_type == choices.FIELD_APP:
            model_class = value.pop('model_class', None)
            if model_class and value.get('object_pk'):
                return get_data_for_model_class(model_class, value.get('object_pk'))
            else:
                return None

        elif obj.field_type == choices.FIELD_FILE:
            return self.storage.url(value)

        return value

    @cached_property
    def storage(self):
        return default_storage

    def get__type(self, obj):
        return f"{super().get__type(obj)}:{obj.field_type}"

    class Meta:
        model = ComponentField
        fields = ('name', 'value', *ModelTypeSerializer.Meta.fields)


class ComponentBlockSerializer(ModelTypeSerializer):
    id = serializers.SerializerMethodField()
    data = serializers.SerializerMethodField()

    def get_id(self, obj):
        return self.context['block_pk']

    def get_data(self, obj):
        return obj.api_fields

    class Meta:
        model = Component
        fields = ('id', 'name', 'slug', 'data', *ModelTypeSerializer.Meta.fields)


class CollectionSerializer(ModelTypeSerializer):
    components = serializers.SerializerMethodField()

    # TODO (rafa): implement a cache layer here.
    def get_components(self, obj):
        # handle include and exclude of components
        include_components = self.context.get('include', None) if self.context else None
        exclude_components = self.context.get('exclude', None) if self.context else None
        include_components = include_components.split(',') if include_components else None
        exclude_components = exclude_components.split(',') if exclude_components else None

        # get current language
        current_lang = translation.get_language()
        default_lang = get_default_lang()

        def get_field_value(field_name, is_translatable, is_multiple):
            if is_translatable:
                translated_slug = build_localized_fieldname(field_name, current_lang)
                value = obj.fields_data_json.get(translated_slug)
                # Fallback to default language
                if not value and current_lang != default_lang:
                    translated_slug = build_localized_fieldname(field_name, default_lang)
                    value = obj.fields_data_json.get(translated_slug)
            else:
                value = obj.fields_data_json.get(field_name)

            # dynamically change value if is_multiple was changed but not the data
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

            return value

        components_with_fields = {}
        component_fields_list = list(get_component_fields_gen(obj))
        model_classes_by_content_type_id = {str(c.id): c.model_class() for c in ContentType.objects.all()}

        # prefetch data
        prefetched = {}
        prefetch_models = {ComponentFieldOption: set(), MediaPhoto: set()}
        for field, field_name, component_field, component, _block_pk in component_fields_list:
            if exclude_components and component.slug in exclude_components:
                continue
            if include_components and component.slug not in include_components:
                continue

            value = get_field_value(field_name, component_field.is_translatable, component_field.is_multiple)
            if not value:
                continue
            if field.field_type in choices.FIELD_OPTION:
                if isinstance(value, list):
                    prefetch_models[ComponentFieldOption].update(value)
                else:
                    prefetch_models[ComponentFieldOption].add(value)
            elif field.field_type == choices.FIELD_IMAGE:
                if isinstance(value, list):
                    prefetch_models[MediaPhoto].update(value)
                else:
                    prefetch_models[MediaPhoto].add(value)
            elif field.field_type == choices.FIELD_CTA:
                model_class = model_classes_by_content_type_id.get(value.get('content_type_id'))
                if value.get('internal', False) and model_class and value.get('object_pk'):
                    if model_class not in prefetch_models:
                        prefetch_models[model_class] = set()
                    prefetch_models[model_class].add(value.get('object_pk'))

            elif field.field_type == choices.FIELD_APP:
                model_class = model_classes_by_content_type_id.get(value.get('content_type_id'))
                if model_class and value.get('object_pk'):
                    if model_class not in prefetch_models:
                        prefetch_models[model_class] = set()
                    if isinstance(value.get('object_pk'), list):
                        prefetch_models[model_class].update(value.get('object_pk'))
                    else:
                        prefetch_models[model_class].add(value.get('object_pk'))

        for model_class, values in prefetch_models.items():
            qs = model_class.objects.filter(pk__in=values)
            if hasattr(model_class, 'default_select_related_fields'):
                qs = qs.select_related(*model_class.default_select_related_fields())
            if hasattr(model_class, 'default_prefetch_related_fields'):
                qs = qs.prefetch_related(*model_class.default_prefetch_related_fields())
            prefetched[model_class] = {str(x.pk): x for x in qs}

        # compose serializer structure
        prev_block_pk = None
        for field, field_name, component_field, component, block_pk in component_fields_list:
            if exclude_components and component.slug in exclude_components:
                continue
            if include_components and component.slug not in include_components:
                continue

            if prev_block_pk != block_pk:
                prev_block_pk = block_pk

            if block_pk not in components_with_fields:
                component.api_fields = {}
                components_with_fields[block_pk] = component

            value = get_field_value(field_name, component_field.is_translatable, component_field.is_multiple)
            if value and field.field_type in [choices.FIELD_CTA, choices.FIELD_APP]:
                value['model_class'] = model_classes_by_content_type_id.get(value.get('content_type_id'))

            field_context = {
                'name': component_field.name,
                'value': value,
                'current_lang': current_lang,
                'prefetched': prefetched,
            }

            components_with_fields[block_pk].api_fields[component_field.slug] = ComponentFieldSerializer(
                field, context=field_context
            ).data

        components_blocks = []
        for block_pk, component in components_with_fields.items():
            components_blocks.append(ComponentBlockSerializer(component, context={'block_pk': block_pk}).data)
        return components_blocks

    def get__type(self, obj):
        return f"{super().get__type(obj)}:{obj.collection_type.slug}"

    class Meta:
        fields = ('components', *ModelTypeSerializer.Meta.fields)
