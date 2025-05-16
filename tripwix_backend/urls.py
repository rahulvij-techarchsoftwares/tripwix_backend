"""
URL configuration for tripwix_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.staticfiles import views
from django.urls import include, path, re_path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework import routers
from rest_framework_simplejwt.views import TokenBlacklistView, TokenObtainPairView, TokenRefreshView, TokenVerifyView

from apps.core.admin import CoreAdminSite
from apps.properties.api.views import WishlistViewSet
from apps.users.views import (
    AppleSignInView,
    GoogleSignInView,
    ResetPasswordAPIView,
    ResetPasswordValidateAPIView,
    UserViewSet,
)

admin.site.__class__ = CoreAdminSite

router = routers.DefaultRouter()
router.register(r'api/v1/wishlist', WishlistViewSet, basename='wishlist')
router.register(r'api/v1/users', UserViewSet, basename='users')

urlpatterns = [
    path('admin/', include("django_admin_kubi.urls")),
    # custom urls per project
    re_path(
        r"^",
        include(("apps.properties.urls", "apps.properties"), namespace="properties"),
    ),
    re_path(
        r"^",
        include(("apps.locations.urls", "apps.locations"), namespace="locations"),
    ),
    path("admin/", admin.site.urls),
    re_path(r"upload/photologue/", include("photologue.urls", namespace="photologue")),
    path("api/v1/properties/", include("apps.properties.api.urls")),
    path("api/v1/pages/", include("apps.pages.urls")),
    path("api/v1/experiences/", include("apps.experiences.urls")),
    path("api/v1/", include("apps.leads.urls")),
    path("api/v1/blog/", include("apps.blogs.urls")),
    # documentation urls
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/schema/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
    path('api/v1/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/v1/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/v1/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('api/v1/token/blacklist/', TokenBlacklistView.as_view(), name='token_blacklist'),
    path('api/v1/auth/google/', GoogleSignInView.as_view(), name="google_login"),
    path('api/v1/auth/apple/', AppleSignInView.as_view(), name="apple-login"),
    path("api/v1/password/validate/", ResetPasswordValidateAPIView.as_view(), name="password-validate"),
    path("api/v1/password-reset/", ResetPasswordAPIView.as_view(), name="password-reset"),
    path('', include(router.urls)),
]

if settings.DEBUG:
    urlpatterns += [
        re_path(r"^static/(?P<path>.*)$", views.serve),
    ]
