from rest_framework import routers

from .views import PageAPIView

router = routers.DefaultRouter()
router.register(r"", PageAPIView, basename="pages")

urlpatterns = [] + router.urls
