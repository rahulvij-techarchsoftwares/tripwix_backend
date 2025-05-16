from rest_framework.decorators import action
from rest_framework.response import Response


class HtmxListModelMixin:
    def get_list_template_name(self):
        return getattr(self, 'list_template_name', None)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.template_name = self.get_list_template_name()
            return response

        serializer = self.get_serializer(queryset, many=True)
        response = Response(serializer.data)
        response.template_name = self.get_list_template_name()
        return response


class HtmxDestroyModelMixin:
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response()

    def perform_destroy(self, instance):
        instance.delete()


class HtmxEditModelMixin:
    def get_edit_template_name(self):
        return getattr(self, 'edit_template_name', None)

    @action(detail=True)
    def edit(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        response = Response(serializer.data)
        response.template_name = self.get_edit_template_name()
        return response
