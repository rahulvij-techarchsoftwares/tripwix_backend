from rest_framework import routers

from .views import ContentAPIView

router = routers.DefaultRouter()
router.register(r"", ContentAPIView, basename="content")

urlpatterns = [] + router.urls
