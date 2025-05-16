from rest_framework import serializers


class SliderItemSerializer(serializers.Serializer):
    title = serializers.CharField()
    caption = serializers.CharField()
    description = serializers.CharField()
    cta_text = serializers.CharField()
    cta_url = serializers.URLField()
    extra_data = serializers.JSONField()
    image = serializers.ImageField()
    mobile_image = serializers.ImageField()
    alt_text_desktop = serializers.CharField()
    alt_text_mobile = serializers.CharField()


class SliderSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    slides = SliderItemSerializer(many=True)
