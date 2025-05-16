from rest_framework import routers

from .views import FormAPIView

router = routers.DefaultRouter()
router.register(r"", FormAPIView, basename="forms")

urlpatterns = [] + router.urls
