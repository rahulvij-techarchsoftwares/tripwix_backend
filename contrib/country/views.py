from cities_light.models import City, Country, Region, SubRegion
from drf_yasg.utils import swagger_auto_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .serializers import (
    CitySerializer,
    CountrySerializer,
    RegionSerializer,
    SimpleRegionSerializer,
    SubRegionSerializer,
)


class CountryAPIView(mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [
        AllowAny,
    ]
    queryset = Country.objects.all()
    serializer_class = CountrySerializer
    http_method_names = [
        "get",
    ]
    paginator = None

    @swagger_auto_schema(responses={status.HTTP_200_OK: SimpleRegionSerializer(many=True)})
    @action(detail=True, methods=['get'])
    def region(self, request, pk=None):
        "Returns the regions under the provided country"
        regions = Region.objects.filter(country_id=pk).select_related('country').order_by('name')
        serializer = SimpleRegionSerializer(regions, many=True, context=self.get_serializer_context())
        return Response(serializer.data)


class RegionAPIView(mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [
        AllowAny,
    ]
    queryset = Region.objects.all()
    serializer_class = RegionSerializer
    http_method_names = [
        "get",
    ]


class SubRegionAPIView(mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [
        AllowAny,
    ]
    queryset = SubRegion.objects.all()
    serializer_class = SubRegionSerializer
    http_method_names = [
        "get",
    ]


class CityAPIView(mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [
        AllowAny,
    ]
    queryset = City.objects.all()
    serializer_class = CitySerializer
    http_method_names = [
        "get",
    ]
