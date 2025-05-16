from rest_framework import mixins, viewsets
from rest_framework.permissions import AllowAny

from .models import Content
from .serializers import ContentSerializer


class ContentAPIView(mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [
        AllowAny,
    ]
    queryset = Content.objects.all()
    serializer_class = ContentSerializer
    http_method_names = [
        "get",
    ]
    lookup_field = "unique_name"
