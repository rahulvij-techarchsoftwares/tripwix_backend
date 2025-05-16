from rest_framework import serializers

from .models import FAQ, FAQCategory


class FAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        fields = ('question', 'answer', 'item_order')


class FAQCategorySerializer(serializers.ModelSerializer):
    faqs = FAQSerializer(many=True)

    class Meta:
        model = FAQCategory
        fields = ('name', 'slug', 'is_active', 'faqs')
