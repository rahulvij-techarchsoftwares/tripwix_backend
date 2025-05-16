from rest_framework import serializers

from apps.core.serializers import HashIDSerializer, serialize_model_object
from apps.media.serializers import MediaPhotoSerializer

from .models import Content


class ContentSerializer(HashIDSerializer, serializers.ModelSerializer):
    data = serializers.SerializerMethodField()
    _type = serializers.SerializerMethodField()

    class Meta:
        model = Content
        fields = ('unique_name', 'title', 'data', '_type')

    def get__type(self, obj):
        return obj.content_type_display()

    def get_data(self, obj):
        if obj.content_type == Content.Types.IMAGE and obj.image_id:
            return MediaPhotoSerializer(obj.image).data
        if obj.content_type == Content.Types.APP:
            return serialize_model_object(obj.content_object)
        if obj.content_type == Content.Types.CONTENT:
            return {"text": obj.content_text}
        return None
