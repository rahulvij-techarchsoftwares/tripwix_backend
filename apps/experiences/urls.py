from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ExperienceViewSet, WishlistExperienceViewSet

router = DefaultRouter()
router.register(r'wishlist', WishlistExperienceViewSet, basename='wishlist-experience')
router.register(r'', ExperienceViewSet, basename='experience')

urlpatterns = [
    path('', include(router.urls)),
]
