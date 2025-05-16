from django.db.models import Q
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.pages.models import Page

from .serializers import PageSerializer, SimplePageSerializer

DEFAULT_CACHE_TIME = 60 * 60 * 6


class PageAPIView(viewsets.GenericViewSet, mixins.RetrieveModelMixin, mixins.ListModelMixin):
    """
    Get Page objects
    """

    permission_classes = [
        AllowAny,
    ]
    serializer_class = PageSerializer
    http_method_names = [
        'get',
    ]

    def get_serializer_class(self):
        if self.action == 'list':
            return SimplePageSerializer
        return self.serializer_class

    def get_queryset(self):
        if self.request.user.is_authenticated and self.request.user.is_staff:
            return Page.objects.all().select_related('collection_type')
        return Page.objects.published().select_related('collection_type')

    def list(self, request, *args, **kwargs):
        return super(PageAPIView, self).list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        return super(PageAPIView, self).retrieve(request, *args, **kwargs)

    @action(detail=False, url_path=r"slug/(?P<slug>[/\w\s.-]+)", url_name='page_by_slug', methods=['get'])
    def slug(self, request, slug=None):
        context = {'include': request.GET.get('include', None), 'exclude': request.GET.get('exclude', None)}
        qs = self.get_queryset()
        slug = slug[:-1] if slug.endswith('/') else slug
        page = qs.filter(Q(slug=slug) | Q(slug=f'{slug}/')).distinct().first()
        if page is None:
            return Response({'detail': 'Page not found'}, status=404)
        return Response(PageSerializer(page, context=context).data, status=200)
