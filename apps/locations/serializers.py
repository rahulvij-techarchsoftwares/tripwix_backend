from rest_framework import serializers

from apps.experiences.models import Experience
from apps.pages.models import Page
from apps.properties.models import Property

from .models import Location, SubLocation


class SubLocationSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.SerializerMethodField()
    image = serializers.ImageField()

    def get_slug(self, obj):
        if not obj.slug:
            return ""

        sublocation_slug = obj.slug
        community_slug = f"communities/{sublocation_slug}"
        page_exists = Page.objects.filter(slug=community_slug, is_active=True).exists()

        if page_exists:
            return sublocation_slug
        return ""


class BaseLocationSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()


class ExperienceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Experience
        fields = ('id', 'title', 'description', 'overview', 'slug')


class LocationPropertySerializer(serializers.ModelSerializer):
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    point = serializers.SerializerMethodField()

    class Meta:
        model = Property
        fields = ('id', 'name', 'latitude', 'longitude', 'point')

    def get_latitude(self, obj):
        if obj.point:
            return obj.point.y  # y is latitude
        return None

    def get_longitude(self, obj):
        if obj.point:
            return obj.point.x  # x is longitude
        return None

    def get_point(self, obj):
        if obj.point:
            return {'type': 'Point', 'coordinates': [obj.point.x, obj.point.y]}
        return None


class LocationSerializer(serializers.ModelSerializer):
    communities = SubLocationSerializer(source='sublocation_set', many=True)
    experiences = ExperienceSerializer(source='experience_set', many=True)
    properties = LocationPropertySerializer(many=True, read_only=True)
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    point = serializers.SerializerMethodField()

    class Meta:
        model = Location
        fields = (
            'id',
            'name',
            'slug',
            'guide_description',
            'when_to_leave',
            'how_to_get_there',
            'good_to_know',
            'latitude',
            'longitude',
            'point',
            'is_active',
            'active_sublocations',
            'sort_order',
            'communities',
            'experiences',
            'properties',
        )

    def get_latitude(self, obj):
        first_property = obj.properties.filter(point__isnull=False).first()
        if first_property and first_property.point:
            return first_property.point.y
        return None

    def get_longitude(self, obj):
        first_property = obj.properties.filter(point__isnull=False).first()
        if first_property and first_property.point:
            return first_property.point.x
        return None

    def get_point(self, obj):
        first_property = obj.properties.filter(point__isnull=False).first()
        if first_property and first_property.point:
            return {'type': 'Point', 'coordinates': [first_property.point.x, first_property.point.y]}
        return None
