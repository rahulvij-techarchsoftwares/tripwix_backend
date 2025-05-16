import json

from django import forms
from django.conf import settings
from django.contrib.admin.widgets import get_select2_language
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from django.forms.widgets import Select, SelectMultiple
from django.urls import reverse
from django.utils.encoding import force_str
from django.utils.translation import gettext_lazy as _

from apps.core.utils import ValidContentTypes


class SortedCheckboxSelectMultiple(forms.CheckboxSelectMultiple):
    template_name = 'admin/widgets/sorted_checkbox_select_multiple.html'
    option_template_name = None

    @property
    def media(self):
        return forms.Media(
            js=(
                'admin/js/force.jquery.js',
                'admin/js/Sortable.min.js',
                'admin/js/sorted_select.js',
                'admin/js/force.jquery.js',
            ),
            css={'screen': ('admin/css/sorted_select.css',)},
        )

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)

        context['widget']['attrs']['class'] = 'sortedm2m'

        return context

    def optgroups(self, name, value, attrs=None):
        # Normalize value to strings
        if value is None:
            value = []
        str_values = [force_str(v) for v in value]

        selected = []
        unselected = []

        for index, (option_value, option_label) in enumerate(self.choices):
            if option_value is None:
                option_value = ''

            if isinstance(option_label, (list, tuple)):
                choices = option_label
            else:
                choices = [(option_value, option_label)]

            for subvalue, sublabel in choices:
                is_selected = str(subvalue) in str_values
                opt = self.create_option(name, subvalue, sublabel, is_selected, str(subvalue), attrs=attrs)
                if is_selected:
                    selected.append(opt)
                else:
                    unselected.append(opt)

        # re-order `selected` list according to str_values order
        ordered = []
        for value in str_values:
            for select in selected:
                if value == str(select['value']):
                    ordered.append(select)
        selected = ordered

        return selected + unselected


class RichEditorWidget(forms.Textarea):
    """
    Default to nothing Rich Editor
    """

    pass


class RichTextEditorSwitcher(object):
    def __new__(cls, attrs=None):
        editor_class = RichEditorWidget

        if hasattr(settings, 'OVERWRITE_RICH_TEXT_EDITOR_WIDGET_CLASS'):
            editor_class = settings.OVERWRITE_RICH_TEXT_EDITOR_WIDGET_CLASS
        else:
            if 'django_admin_kubi' in settings.INSTALLED_APPS:
                from django_admin_kubi.widgets import RichTextEditorWidget as KubiTextWidget

                editor_class = KubiTextWidget

        instance = super(editor_class, editor_class).__new__(editor_class)
        if editor_class != cls:
            instance.__init__(attrs=attrs)
        return instance


class RichTextEditorWidget(RichTextEditorSwitcher):
    pass


class ColorWidget(forms.widgets.TextInput):
    input_type = 'color'


class PhoneNumberWidget(forms.widgets.TextInput):
    template_name = 'admin/widgets/phone_number.html'

    @property
    def media(self):
        return forms.Media(
            js=('admin/js/intlTelInput.min.js',),
            css={'screen': ('admin/css/intlTelInput.css',)},
        )


class SlugWidget(forms.widgets.TextInput):
    template_name = 'admin/widgets/slug.html'
    model = None
    url = None
    lang = None

    def __init__(self, *args, **kwargs):
        if 'model' in kwargs:
            self.model = kwargs['model']
            del kwargs['model']

        if 'url' in kwargs:
            self.url = kwargs['url']
            del kwargs['url']

        if 'lang' in kwargs:
            self.lang = kwargs['lang']
            del kwargs['lang']

        super(SlugWidget, self).__init__(*args, **kwargs)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)

        if self.model and hasattr(self.model, 'get_base_url'):
            url = self.model.get_base_url(lang=self.lang)
            if not url.endswith('/'):
                url = f'{url}/'
            context['widget']['url'] = url
            return context
        elif self.url and isinstance(self.url, str):
            url = self.url
        else:
            url = getattr(settings, 'PROJECT_URL', "https://example.com/")

        if not url.endswith('/'):
            url = f'{url}/'

        if self.lang:
            url = f'{url}{self.lang}/'
        context['widget']['url'] = url
        return context


class VisibilityWidget(forms.CheckboxInput):
    template_name = 'admin/widgets/visibility.html'

    @property
    def media(self):
        return forms.Media(
            js=(
                "admin/js/jquery.init.js",
                "admin/js/visibility-widget.js",
            ),
        )


class AppWidget(forms.widgets.TextInput):
    template_name = 'admin/widgets/app.html'
    url_name = "%s:apps-autocomplete"

    def __init__(
        self, attrs=None, app_model=None, ignore_list=[], content_type_field=None, object_field=None, is_multiple=False
    ):
        self.attrs = {} if attrs is None else attrs.copy()
        self.ignore_list = ignore_list
        self.app_model = app_model
        self.i18n_name = get_select2_language()
        self.content_type_field = content_type_field
        self.object_field = object_field
        self.is_multiple = is_multiple

    def get_url(self):
        return reverse(self.url_name % 'admin')

    def build_select2_attrs(self):
        """
        Set select2's AJAX attributes.
        Attributes can be set using the html5 data attribute.
        Nested attributes require a double dash as per
        https://select2.org/configuration/data-attributes#nested-subkey-options
        """
        attrs = {}
        attrs.setdefault("class", "")
        attrs.update(
            {
                "data-ajax--cache": "true",
                "data-ajax--delay": 250,
                "data-ajax--type": "GET",
                "data-ajax--url": self.get_url(),
                "data-theme": "admin-autocomplete",
                "data-allow-clear": json.dumps(not self.is_required),
                "data-placeholder": "",  # Allows clearing of the input.
                "data-content-field": self.content_type_field,
                "data-object-field": self.object_field,
                "lang": self.i18n_name,
                "class": attrs["class"] + (" " if attrs["class"] else "") + "admin-autocomplete",
            }
        )
        return attrs

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['select2_attrs'] = self.build_select2_attrs()
        context['is_multiple'] = self.is_multiple
        # get selected object
        if value:
            content_type_objects = []
            try:
                data_dict = json.loads(value)
                content_type = ContentType.objects.get(id=data_dict.get('content_type_id'))
                if self.app_model and self.app_model.pk != content_type.pk:
                    content_type_objects = []
                else:
                    if isinstance(data_dict.get('object_pk'), list):
                        content_type_objects = content_type.get_all_objects_for_this_type(
                            id__in=data_dict.get('object_pk')
                        )
                    else:
                        content_type_objects = [
                            content_type.get_object_for_this_type(id=data_dict.get('object_pk')),
                        ]
            except Exception:
                pass

            if content_type_objects:
                context['selected_objects'] = [(str(getattr(obj, 'pk')), str(obj)) for obj in content_type_objects]

        if self.app_model:
            context['single_app'] = True
            context['available_apps'] = [
                (self.app_model.id, self.app_model),
            ]
        else:
            context['single_app'] = False
            empty_selection = [
                ('', '-------------------'),
            ]
            context['available_apps'] = empty_selection + [
                (app.id, app) for app in ValidContentTypes(ignore_list=self.ignore_list, is_searchable=True).fetch()
            ]

        return context

    @property
    def media(self):
        extra = "" if settings.DEBUG else ".min"
        i18n_file = ("admin/js/vendor/select2/i18n/%s.js" % self.i18n_name,) if self.i18n_name else ()
        return forms.Media(
            js=(
                "admin/js/vendor/jquery/jquery%s.js" % extra,
                "admin/js/vendor/select2/select2.full%s.js" % extra,
            )
            + i18n_file
            + (
                "admin/js/jquery.init.js",
                "admin/js/app-widget.js",
            ),
            css={
                "screen": (
                    "admin/css/vendor/select2/select2%s.css" % extra,
                    "admin/css/autocomplete.css",
                ),
            },
        )


class CTAWidget(AppWidget):
    template_name = 'admin/widgets/cta.html'

    @property
    def media(self):
        extra = "" if settings.DEBUG else ".min"
        i18n_file = ("admin/js/vendor/select2/i18n/%s.js" % self.i18n_name,) if self.i18n_name else ()
        return forms.Media(
            js=(
                "admin/js/vendor/jquery/jquery%s.js" % extra,
                "admin/js/vendor/select2/select2.full%s.js" % extra,
            )
            + i18n_file
            + (
                "admin/js/jquery.init.js",
                'admin/js/cta-widget.js',
            ),
            css={
                "screen": (
                    "admin/css/vendor/select2/select2%s.css" % extra,
                    "admin/css/autocomplete.css",
                ),
            },
        )


class SelectizeWidget(Select):
    template_name = 'admin/widgets/selectize.html'
    option_template_name = 'admin/widgets/selectize_option.html'
    add_to = None
    add_url = None
    load_from = None
    load_url = None
    persist = None
    value_field = None
    label_field = None
    search_field = None
    sort_field = 'text'
    preload = False

    @property
    def media(self):
        return forms.Media(
            js=(
                'admin/js/selectize.min.js',
                'admin/js/selectize.init.js',
            ),
            css={'screen': ('admin/css/vendor/selectize.theme.css',)},
        )

    def __init__(self, *args, **kwargs):
        if 'add_to' in kwargs:
            self.add_to = kwargs.pop('add_to')
        if 'add_url' in kwargs:
            self.add_url = kwargs.pop('add_url')
        if 'load_from' in kwargs:
            self.load_from = kwargs.pop('load_from')
        if 'load_url' in kwargs:
            self.load_url = kwargs.pop('load_url')
        super(SelectizeWidget, self).__init__(*args, **kwargs)

    def get_selectize_render(self):
        return None

    def get_option_data(self, option):
        return {}

    def get_placeholder(self):
        return _('e.g.: Music, Color, Brand ...')

    def create_option(self, *args, **kwargs):
        option = super(SelectizeWidget, self).create_option(*args, **kwargs)
        option_data = self.get_option_data(option)
        if option_data:
            option['attrs'] = {'data-data': option_data}
        return option

    def get_on_init_function(self, name, value):
        """
        this will be included in the js onInitialize: function(){ ... }
        """
        return ""

    def get_on_change_function(self, name, value):
        """
        this will be included in the js onChange: function(value){ ... }
        """
        return ""

    def get_context(self, name, value, attrs):
        from django.contrib import admin

        # Get default widget context
        context = super(SelectizeWidget, self).get_context(name, value, attrs)

        # add default placeholder
        if "placeholder" not in context['widget']['attrs']:
            context['widget']['attrs']['placeholder'] = self.get_placeholder()

        if 'data-selectize' not in context['widget']['attrs']:
            context['widget']['attrs']['data-selectize'] = 'true'

        if self.value_field and 'data-value-field' not in context['widget']['attrs']:
            context['widget']['attrs']['data-value-field'] = self.value_field

        if self.label_field and 'data-label-field' not in context['widget']['attrs']:
            context['widget']['attrs']['data-label-field'] = self.label_field

        if self.search_field and 'data-search-field' not in context['widget']['attrs']:
            context['widget']['attrs']['data-search-field'] = self.search_field

        if self.sort_field and 'data-sort-field' not in context['widget']['attrs']:
            context['widget']['attrs']['data-sort-field'] = self.sort_field

        if self.persist and 'data-persist' not in context['widget']['attrs']:
            context['widget']['attrs']['data-persist'] = self.persist

        if self.preload and 'data-preload' not in context['widget']['attrs']:
            context['widget']['attrs']['data-preload'] = "focus"

        if self.add_to and not self.add_url:
            try:
                model_admin = admin.site._registry[self.add_to]
            except KeyError:
                raise ImproperlyConfigured("to use add_to %s model must be registered in admin" % self.add_to.__name__)

            if not hasattr(model_admin, 'get_selectize_ajax_add_url'):
                raise ImproperlyConfigured(
                    "%s has no 'get_selectize_ajax_add_url' method, (required to fetch objects with selectize widget)"
                    % model_admin.__class__.__name__
                )
            else:
                self.add_url = model_admin.get_selectize_ajax_add_url()

        if self.add_url and 'data-add-url' not in context['widget']['attrs']:
            context['widget']['attrs']['data-add-url'] = self.add_url

        if self.load_from and not self.load_url:
            try:
                model_admin = admin.site._registry[self.load_from]
            except KeyError:
                raise ImproperlyConfigured(
                    "to use load_from %s model must be registered in admin" % self.load_from.__name__
                )

            if not hasattr(model_admin, 'get_selectize_ajax_load_url'):
                raise ImproperlyConfigured(
                    "%s has no 'get_selectize_ajax_load_url' method, (required to fetch objects with selectize widget)"
                    % model_admin.__class__.__name__
                )
            else:
                self.load_url = model_admin.get_selectize_ajax_load_url()

        if self.load_url and 'data-load-url' not in context['widget']['attrs']:
            context['widget']['attrs']['data-load-url'] = self.load_url
            context['widget']['has_load_url'] = True
        else:
            context['widget']['has_load_url'] = False

        on_init_function = self.get_on_init_function(name, value)
        if on_init_function:
            context['widget']['attrs']['data-on-initialize'] = on_init_function

        on_change_function = self.get_on_change_function(name, value)
        if on_change_function:
            context['widget']['attrs']['data-on-change'] = on_change_function

        if 'data-error-message' not in context['widget']['attrs']:
            context['widget']['attrs']['data-error-message'] = _('Ups, something went wrong, could not add item.')

        context['selectize_render'] = self.get_selectize_render()
        return context


class SelectizeMultipleWidget(SelectizeWidget, SelectMultiple):
    pass
