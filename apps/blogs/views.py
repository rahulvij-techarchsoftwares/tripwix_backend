from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Article, Author, Topic
from .serializers import ArticleDetailSerializer, ArticleSerializer, AuthorSerializer, TopicSerializer


class ArticleViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ArticleSerializer
    queryset = Article.objects.filter(is_active=True).order_by('-created_at')
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['tag']

    def get_queryset(self):
        queryset = super().get_queryset()
        filter_param = self.request.query_params.get('filter')

        if filter_param:
            queryset = queryset.filter(category=filter_param)

        return queryset

    def get_serializer_class(self):
        if self.action in ('retrieve', 'slug'):
            return ArticleDetailSerializer
        return super().get_serializer_class()

    @action(detail=False, url_path=r'slug/(?P<slug>[/\w\s.-]+)', url_name='blog_by_slug', methods=['get'])
    def slug(self, request, slug=None):
        context = {'include': request.GET.get('include', None), 'exclude': request.GET.get('exclude', None)}
        qs = self.get_queryset()
        slug = slug.rstrip('/')
        blog_instance = qs.filter(Q(slug=slug) | Q(slug=f'{slug}/')).first()

        if blog_instance is None:
            return Response({'detail': 'Blog page not found'}, status=404)

        return Response(self.get_serializer(blog_instance, context=context).data, status=200)


class AuthorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer


class TopicViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Topic.objects.all()
    serializer_class = TopicSerializer
