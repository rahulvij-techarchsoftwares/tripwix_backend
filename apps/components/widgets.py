import json

from django import forms
from django.conf import settings
from django.forms import MultiWidget
from django.forms.widgets import CheckboxInput, FileInput, HiddenInput, Select, TextInput
from django.urls import reverse
from django.utils.encoding import force_str
from django.utils.html import conditional_escape, escape
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from apps.core.utils import get_translation_fields
from apps.core.widgets import SelectizeWidget
from apps.media.models import MediaPhoto
from apps.media.widgets import ImageWidget


class CharFieldWidget(TextInput):
    template_name = 'widgets/charfield_widget.html'

    @property
    def media(self):
        return forms.Media(
            js=(
                "admin/js/jquery.init.js",
                'admin/js/component-widgets.init.js',
            )
        )


class ModelLinkWidget(HiddenInput):
    template_name = 'widgets/model_link_widget.html'

    def __init__(self, obj, attrs=None):
        self.object = obj
        super(ModelLinkWidget, self).__init__(attrs)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget']['app_obj'] = self.object
        context['widget']['app_obj_meta'] = self.object._meta
        return context


class ComponentFieldSelectizeWidget(SelectizeWidget):
    def __init__(self, *args, **kwargs):
        super(ComponentFieldSelectizeWidget, self).__init__(*args, **kwargs)

    def get_placeholder(self):
        return ''


class CollectionSelectizeWidget(SelectizeWidget):
    def __init__(self, *args, **kwargs):
        # TODO: this should be dynamic
        from apps.pages.models import Page

        self.load_from = Page
        super(CollectionSelectizeWidget, self).__init__(*args, **kwargs)

    def get_option_data(self, option):
        page = option['label']
        data = {'page_url': page.get_absolute_url()}
        return json.dumps(data)

    def get_placeholder(self):
        return _('Search for a page title')
