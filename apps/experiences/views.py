from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, viewsets

from .models import Experience, WishlistExperience
from .serializers import ExperienceSerializer, WishlistExperienceSerializer


class ExperienceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Experience.objects.all()
    serializer_class = ExperienceSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['location', 'activity']


class WishlistExperienceViewSet(viewsets.ModelViewSet):
    serializer_class = WishlistExperienceSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_queryset(self):
        return WishlistExperience.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save()
