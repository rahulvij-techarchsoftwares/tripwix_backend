from rest_framework.negotiation import DefaultContentNegotiation


class HtmxContentNegotiation(DefaultContentNegotiation):
    def select_renderer(self, request, renderers, format_suffix=None):
        if request.META.get('HTTP_HX_REQUEST', 'false') == 'true':
            renderers = self.filter_renderers(renderers, 'htmx')
            for renderer in renderers:
                return renderer, 'text/htmx'

        return super().select_renderer(request, renderers, format_suffix=format_suffix)
