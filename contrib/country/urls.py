from rest_framework import routers

from .views import CityAPIView, CountryAPIView, RegionAPIView, SubRegionAPIView

router = routers.DefaultRouter()
router.register(r"region", RegionAPIView, basename="region")
router.register(r"sub-region", SubRegionAPIView, basename="sub-region")
router.register(r"city", CityAPIView, basename="city")
router.register(r"", CountryAPIView, basename="country")


urlpatterns = [] + router.urls
