from rest_framework import serializers

from apps.experiences.models import Activity, Experience, Inclusion, WishlistExperience
from apps.locations.models import Location


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ['id', 'name', 'slug']


class ActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Activity
        fields = ['id', 'name']


class InclusionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Inclusion
        fields = ['id', 'description']


class ExperienceSerializer(serializers.ModelSerializer):
    activities = ActivitySerializer(many=True, read_only=True)
    location = LocationSerializer(read_only=True)
    inclusions = InclusionSerializer(many=True, read_only=True)

    class Meta:
        model = Experience
        fields = ['id', 'title', 'slug', 'description', 'overview', 'image', 'activities', 'location', 'inclusions']


class WishlistExperienceSerializer(serializers.ModelSerializer):
    experience_id = serializers.PrimaryKeyRelatedField(
        source='experiences',
        queryset=Experience.objects.all(),
        write_only=True,
    )

    class Meta:
        model = WishlistExperience
        fields = ['id', 'experience_id', 'experiences']
        read_only_fields = ['experiences']

    def create(self, validated_data):
        experience = validated_data.pop('experiences')
        user = self.context['request'].user

        wishlist, _ = WishlistExperience.objects.get_or_create(user=user)
        wishlist.experiences.add(experience)
        return wishlist
