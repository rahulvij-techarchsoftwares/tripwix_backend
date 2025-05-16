from apps.components.serializers import CollectionSerializer, CollectionTypeSerializer
from apps.core.serializers import ModelTypeSerializer, SeoSerializerMixin, SlugSerializerMixin

from .models import Page


class SimplePageSerializer(ModelTypeSerializer, SeoSerializerMixin, SlugSerializerMixin):
    collection_type = CollectionTypeSerializer()

    def get__type(self, obj):
        return f"{super().get__type(obj)}:{obj.collection_type.slug}"

    class Meta:
        model = Page
        fields = (
            'id',
            'title',
            *SlugSerializerMixin.Meta.fields,
            *SeoSerializerMixin.Meta.fields,
            'collection_type',
            *ModelTypeSerializer.Meta.fields,
        )


class PageSerializer(CollectionSerializer, SeoSerializerMixin, SlugSerializerMixin):
    collection_type = CollectionTypeSerializer()

    class Meta:
        model = Page
        fields = (
            'id',
            'title',
            *SlugSerializerMixin.Meta.fields,
            *SeoSerializerMixin.Meta.fields,
            'collection_type',
            *CollectionSerializer.Meta.fields,
        )
