from cities_light.models import City, Country, Region, SubRegion
from rest_framework import serializers


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = [
            "id",
            "name",
            "code2",
        ]


class SimpleRegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Region
        fields = ["id", "name", "geoname_code"]


class RegionSerializer(serializers.ModelSerializer):
    country = CountrySerializer()

    class Meta:
        model = Region
        fields = [
            "id",
            "name",
            "geoname_code",
            "country",
        ]


class SubRegionSerializer(serializers.ModelSerializer):
    country = CountrySerializer()
    region = RegionSerializer()

    class Meta:
        model = SubRegion
        fields = ["id", "name", "geoname_code", "country", "region"]


class CitySerializer(serializers.ModelSerializer):
    country = CountrySerializer()
    region = RegionSerializer()
    subregion = SubRegionSerializer()

    class Meta:
        model = City
        fields = [
            "id",
            "name",
            "display_name",
            "latitude",
            "longitude",
            "subregion",
            "region",
            "country",
        ]
