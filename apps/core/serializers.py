from hashid_field.rest import HashidSerializerCharField
from rest_framework import serializers

from .utils import build_localized_fieldname, domain_with_proto, get_translation_fields


def serialize_model_object(model_obj):
    if model_obj and 'get_model_serializer' in dir(model_obj.__class__):
        app_model_serializer = model_obj.__class__.get_model_serializer(model_obj)
        return app_model_serializer(model_obj).data


class ModelTypeSerializer(serializers.ModelSerializer):
    _type = serializers.CharField(default='mediaphoto')

    def get__type(self, obj):
        return self.Meta.model._meta.model_name

    class Meta:
        model = None
        fields = ('_type',)


class HashIDSerializer(serializers.Serializer):
    id = HashidSerializerCharField(read_only=True)


class SeoSerializerMixin(serializers.Serializer):
    seo = serializers.SerializerMethodField(method_name='get_seo')

    def get_seo(self, obj):
        return {
            'title': obj.seo_title,
            'description': obj.seo_description,
            'image': obj.seo_image.url if obj.seo_image else None,
        }

    class Meta:
        fields = ('seo',)


class SlugSerializerMixin(serializers.Serializer):
    url = serializers.SerializerMethodField(method_name='get_url')

    def get_url(self, obj):
        fields = list(self.get_fields())
        url_languages = {}
        base_url = domain_with_proto()
        if base_url.endswith('/'):
            base_url = base_url[:-1]
        if 'slug' in fields:
            for trans_field in get_translation_fields('slug'):
                lang = trans_field.split("_")[-1]

                try:
                    lang_slug = getattr(obj, trans_field)

                except AttributeError:
                    lang_slug = getattr(obj, 'slug')

                if lang_slug:
                    url_languages[lang] = f'{base_url}/{lang}/{lang_slug}'

            return url_languages

        else:
            return url_languages

    class Meta:
        fields = (
            'slug',
            'url',
        )
