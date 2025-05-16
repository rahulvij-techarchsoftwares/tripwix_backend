from django.urls import re_path
from rest_framework.routers import DefaultRouter

from . import views

app_name = 'properties'

router = DefaultRouter()
router.register(r'', views.PropertyViewSet, basename='property')
router.register(r'ambassador', views.AmbassadorViewSet, basename='ambassador')

urlpatterns = [
    re_path('filters/', views.PropertyFiltersAPIView.as_view(), name='property-filters'),
    re_path(
        "notification/",
        views.GoogleAPINotificationView.as_view(),
        name="google-notification",
    ),
    re_path('hostify_webhook/', views.PropertyCalendarWebhookView.as_view(), name='hostify-webhook'),
] + router.urls
