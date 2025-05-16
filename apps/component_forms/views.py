from django.db.models import Q
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import ComponentForm
from .serializers import ComponentFormDataSerializer, ComponentFormSerializer, SimpleComponentFormSerializer

DEFAULT_CACHE_TIME = 60 * 60 * 6


class FormAPIView(viewsets.GenericViewSet, mixins.ListModelMixin):
    """
    Get Form objects
    """

    permission_classes = [
        AllowAny,
    ]
    serializer_class = ComponentFormSerializer
    http_method_names = ['get', 'post']

    def get_serializer_class(self):
        if self.action == 'list':
            return SimpleComponentFormSerializer
        return self.serializer_class

    def get_queryset(self):
        if self.request.user.is_authenticated and self.request.user.is_staff:
            return ComponentForm.objects.all()
        return ComponentForm.objects.published()

    def list(self, request, *args, **kwargs):
        return super(FormAPIView, self).list(request, *args, **kwargs)

    @action(detail=False, url_path=r"slug/(?P<slug>[/\w\s.-]+)", url_name='form_by_slug', methods=['get', 'post'])
    def slug(self, request, slug=None):
        qs = self.get_queryset()
        slug = slug[:-1] if slug.endswith('/') else slug
        component_form = qs.filter(Q(slug=slug) | Q(slug=f'{slug}/')).distinct().first()
        if component_form is None:
            return Response({'detail': 'Form not found'}, status=404)

        # handle form submission
        if request.method == 'POST':
            data_validation = ComponentFormDataSerializer(data=request.data, component_form=component_form)
            data_validation.is_valid(raise_exception=True)
            # TODO: do some kind of action
            # we can send email, we can store in a lead
            return Response(data_validation.data, status=201)

        return Response(ComponentFormSerializer(component_form).data, status=200)
