from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import Http404
from rest_framework.renderers import TemplateHTMLRenderer


class HtmxRenderer(TemplateHTMLRenderer):
    media_type = 'text/htmx'
    format = 'htmx'
    template_name = None

    def render(self, data, accepted_media_type=None, renderer_context=None):
        template_context = self.get_template_context(data, renderer_context)
        action = template_context['api_meta'].get('action')
        try:
            if action == 'list':
                render_output = ''
                for item in data['results']:
                    render_output += super().render({'obj': item}, accepted_media_type, renderer_context)
                return render_output
            elif action == 'destroy':
                return ''
            else:
                data = {'obj': data}

            return super().render(data, accepted_media_type, renderer_context)
        except ImproperlyConfigured as e:
            raise Http404(e)

    def get_template_context(self, data, renderer_context):
        response = renderer_context['response']
        view = renderer_context['view']
        if data and response.exception:
            data['status_code'] = response.status_code
        # get original view template name
        if data is None:
            data = {}

        data['api_meta'] = {
            'action': getattr(view, 'action'),
            'template_name': getattr(view, 'template_name'),
        }
        return data
