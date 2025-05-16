from apps.core.serializers import ModelTypeSerializer
from apps.media.models import MediaDocument, MediaPhoto


class MediaPhotoSerializer(ModelTypeSerializer):
    class Meta:
        model = MediaPhoto
        fields = ('image', 'caption', *ModelTypeSerializer.Meta.fields)


class SimpleMediaPhotoSerializer(ModelTypeSerializer):
    class Meta:
        model = MediaPhoto
        fields = ('image', 'caption', *ModelTypeSerializer.Meta.fields)


class SimpleMediaDocumentSerializer(ModelTypeSerializer):
    class Meta:
        model = MediaDocument
        fields = ('title', 'description', 'file_object', *ModelTypeSerializer.Meta.fields)
