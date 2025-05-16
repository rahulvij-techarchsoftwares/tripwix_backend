import json
from itertools import chain

import six
from django import forms
from django.conf import settings
from django.contrib.gis.forms.widgets import BaseGeometryWidget
from django.core.exceptions import ImproperlyConfigured
from django.forms.utils import flatatt
from django.forms.widgets import Select, SelectMultiple
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.utils.encoding import force_str
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe
from django_admin_kubi.widgets import TinyMceEditorWidget

from apps.locations.models import Location

from .models import Property


class SlugWidget(forms.widgets.TextInput):
    url = None

    def __init__(self, *args, **kwargs):
        if 'url' in kwargs:
            self.url = kwargs['url']
            del kwargs['url']
        super().__init__(*args, **kwargs)

    def render(self, name, value, attrs=None, renderer=None):
        if self.url and hasattr(self.url, 'get_base_url'):
            url = self.url.get_base_url()
        elif self.url and isinstance(self.url, str):
            url = self.url
        else:
            url = getattr(settings, 'PROJECT_URL', "http://example.com/")

        if value is None:
            value = ''
        final_attrs = self.build_attrs(attrs, {'type': self.input_type, 'name': name})
        if value != '':
            # Only add the 'value' attribute if a value is non-empty.
            final_attrs['value'] = force_str(self.format_value(value))
        return format_html(
            u'<div class="input-group"><span class="input-group-addon">{0}</span><input{1} /></div>',
            url,
            flatatt(final_attrs),
        )


class BaseSelectizeWidget(Select):
    template_name = 'admin/widgets/selectize.html'

    def __init__(self, add_to=None, *args, **kwargs):
        self.add_to = add_to
        super().__init__(*args, **kwargs)

    def render(self, name, value, attrs=None, choices=(), renderer=None):
        from django.contrib import admin

        if attrs is None:
            attrs = {}

        # SET NO RESULTS TEXT
        output = super().render(name, value, attrs, renderer=None)

        add_url = ''
        if not self.add_to:
            add_url = ''
        elif self.add_to in admin.site._registry:
            model_admin = admin.site._registry[self.add_to]
            if not hasattr(model_admin, 'get_ajax_add_url'):
                raise ImproperlyConfigured(
                    "%s has no 'get_ajax_add_url' method, (required t add new models with selectize widget)"
                    % model_admin.__class__.__name__
                )
            add_url = model_admin.get_ajax_add_url()
        else:
            raise ImproperlyConfigured(
                "%s is not register in the admin, (required to add new models with selectize widget)"
                % self.add_to.__name__
            )
        if self.add_to and add_url:
            create = u"""
                create: function(input) {
                    var csrf_token = $(":input[name='csrfmiddlewaretoken']").val();
                    $.ajax({
                        url: "%(url)s",
                        type: 'POST',
                        dataType: 'json',
                        data: {
                            input: input,
                            csrfmiddlewaretoken: csrf_token
                        },
                        error: function() {
                            alert("%(error_msg)s");
                        },
                        success: function(res) {
                            var control = $("#%(id)s")[0].selectize;
                            control.addOption(res);
                            control.setValue(res.value);
                        }
                    });

                    return false;
                }
            """ % {
                'id': attrs['id'],
                'url': add_url,
                'error_msg': 'Ups, something went wrong, could not add item.',
            }
        else:
            create = ""

        if "__prefix__" in name:
            script = ""
        else:
            script = u"""
                <script type="text/javascript">
                (function ($,window) {
                    $(document).ready(function() {
                        $("#%(id)s").selectize({
                            sortField: 'text',
                            %(create)s
                        });

                    });
                })(django.jQuery, window);
                </script>
            """ % {
                'id': attrs['id'],
                'create': create,
            }

        return format_html(u'{0}\n{1}', output, mark_safe(script))


class SelectizeWidget(BaseSelectizeWidget):
    @property
    def media(self):
        js = ["admin/js/selectize.min.js"]
        css = ["admin/css/selectize.theme.css"]
        return forms.Media(
            js=[static("%s" % path) for path in js], css={"screen": [static("%s" % path) for path in css]}
        )


class MySelectizeWidget(SelectizeWidget):
    def __init__(self, attrs=None, choices=(), underscore_template=False):
        super().__init__(attrs=attrs, choices=choices)

    @property
    def media(self):
        js = ["admin/js/selectize.min.js"]

        css = ["admin/css/selectize.theme.css"]
        return forms.Media(
            js=[static("%s" % path) for path in js], css={"screen": [static("%s" % path) for path in css]}
        )

    def render(self, name, value, attrs=None, renderer=None):
        from django.contrib import admin

        if attrs is None:
            attrs = {}

        # SET NO RESULTS TEXT
        output = super().render(name, value, attrs, renderer)

        add_url = ''
        if not self.add_to:
            add_url = ''
        elif self.add_to in admin.site._registry:
            model_admin = admin.site._registry[self.add_to]
            if not hasattr(model_admin, 'get_ajax_add_url'):
                raise ImproperlyConfigured(
                    "%s has no 'get_ajax_add_url' method, (required t add new models with selectize widget)"
                    % model_admin.__class__.__name__
                )
            add_url = model_admin.get_ajax_add_url()
        else:
            raise ImproperlyConfigured(
                "%s is not register in the admin, (required to add new models with selectize widget)"
                % self.add_to.__name__
            )
        if self.add_to and add_url:
            create = u"""
                create: function(input) {
                    var csrf_token = $(":input[name='csrfmiddlewaretoken']").val();
                    $.ajax({
                        url: "%(url)s",
                        type: 'POST',
                        dataType: 'json',
                        data: {
                            input: input,
                            csrfmiddlewaretoken: csrf_token
                        },
                        error: function() {
                            alert("%(error_msg)s");
                        },
                        success: function(res) {
                            var control = $("#%(id)s")[0].selectize;
                            control.addOption(res);
                            control.setValue(res.value);
                        }
                    });

                    return false;
                }
            """ % {
                'id': attrs['id'],
                'url': add_url,
                'error_msg': 'Ups, something went wrong, could not add item.',
            }
        else:
            create = ""

        if "__prefix__" in name:
            script = ""
        else:
            script = u"""
                <script type="text/javascript">
                !function ($,window) {
                    $(document).ready(function() {
                        $("#%(id)s").selectize({
                            // sortField: 'text',
                            %(create)s
                        });

                    });
                
                }(django.jQuery, window);
                </script>
            """ % {
                'id': attrs['id'],
                'create': create,
            }

        return format_html(u'{0}\n{1}', output, mark_safe(script))


class SimpleSelectizeMultipleWidget(BaseSelectizeWidget):
    allow_multiple_selected = True
    template_name = 'admin/widgets/selectize_multiple.html'

    def __init__(
        self,
        add_to=None,
        attrs=None,
        choices=(),
        underscore_template=False,
        instance=None,
    ):
        self.add_to = add_to
        self.instance = instance
        self.underscore_template = underscore_template
        super().__init__(attrs=attrs, choices=choices)

    @property
    def media(self):
        js = [
            "admin/js/selectizeMultiple.init.js",
        ]
        css = ["admin/css/selectize.theme.css"]
        return forms.Media(
            js=[static("%s" % path) for path in js], css={"screen": [static("%s" % path) for path in css]}
        )

    def value_from_datadict(self, data, files, name):
        values = [v for v in super().value_from_datadict(data, files, name) if v]
        return values

    def render(self, name, value, attrs=None, choices=tuple(), renderer=None):
        from django.contrib import admin

        if attrs is None:
            attrs = {}

        # SET NO RESULTS TEXT
        output = super().render(name, value, attrs, renderer)
        position = output.find('</select>')

        select_all_list = [
            'id_agents',
        ]
        for key, value in attrs.items():
            attr_value = value
        if attr_value in select_all_list:
            output = mark_safe(
                output[:position]
                + '<option value ="0"> Select All</option>\n'
                + '<option value ="-1"> None</option>\n'
                + output[position:]
            )

        add_to = self.attrs.get('add_to', None)
        if not add_to:
            add_url = ''
        elif add_to in admin.site._registry:
            model_admin = admin.site._registry[add_to]

            if not hasattr(model_admin, 'get_ajax_add_url'):
                raise ImproperlyConfigured(
                    "%s has no 'get_ajax_add_url' method, (required t add new models with selectize widget)"
                    % model_admin.__class__.__name__
                )

            add_url = model_admin.get_ajax_add_url()
        else:
            raise ImproperlyConfigured(
                "%s is not register in the admin, (required to add new models with selectize widget)" % add_to.__name__
            )

        if add_to and add_url:
            create = u"""
                create: function(input) {
                    var csrf_token = $(":input[name='csrfmiddlewaretoken']").val();
                    $.ajax({
                        url: "%(url)s",
                        type: 'POST',
                        dataType: 'json',
                        data: {
                            input: input,
                            csrfmiddlewaretoken: csrf_token
                        },
                        error: function() {
                            alert("%(error_msg)s");
                        },
                        success: function(res) {
                            var control = $("#%(id)s")[0].selectize;
                            control.addOption(res);
                            control.setValue(res.value);
                        }
                    });

                    return false;
                }
            """ % {
                'id': attrs['id'],
                'url': add_url,
                'error_msg': 'Ups, something went wrong, could not add item.',
            }
        else:
            create = ""

        if "__prefix__" in name:
            script = ""
        else:
            script = u"""
                <script type="text/javascript">
                    $(document).ready(function() {
                        $("#%(id)s").selectize({
                            plugins: ['remove_button', ], //  'drag_drop' 'restore_on_backspace'
                            sortField: 'text',
                            %(create)s
                        });
                    });
                </script>
            """ % {
                'id': attrs['id'],
                'create': create,
            }

        return format_html(u'{0}\n{1}', output, mark_safe(script))


class MySelectizeMultipleWidget(BaseSelectizeWidget):
    allow_multiple_selected = True
    template_name = 'admin/widgets/selectize_multiple.html'

    def __init__(
        self,
        add_to=None,
        attrs=None,
        choices=(),
        underscore_template=False,
        instance=None,
    ):
        self.add_to = add_to
        self.instance = instance
        self.underscore_template = underscore_template
        super().__init__(attrs=attrs, choices=choices)

    @property
    def media(self):
        js = [
            "admin/js/selectizeMultiple.init.js",
            "admin/js/submitSelectize.js",
            "admin/js/getSelectedAmenities.js",
        ]
        css = ["admin/css/selectize.theme.css"]
        return forms.Media(
            js=[static("%s" % path) for path in js], css={"screen": [static("%s" % path) for path in css]}
        )

    def value_from_datadict(self, data, files, name):
        values = [v for v in super().value_from_datadict(data, files, name) if v]
        return values

    def render(self, name, value, attrs=None, choices=tuple(), renderer=None):
        from django.contrib import admin

        if attrs is None:
            attrs = {}

        # SET NO RESULTS TEXT
        output = super().render(name, value, attrs, renderer)
        position = output.find('</select>')

        select_all_list = [
            'id_agents',
        ]
        for key, value in attrs.items():
            attr_value = value
        if attr_value in select_all_list:
            output = mark_safe(
                output[:position]
                + '<option value ="0"> Select All</option>\n'
                + '<option value ="-1"> None</option>\n'
                + output[position:]
            )

        add_to = self.attrs.get('add_to', None)
        if not add_to:
            add_url = ''
        elif add_to in admin.site._registry:
            model_admin = admin.site._registry[add_to]

            if not hasattr(model_admin, 'get_ajax_add_url'):
                raise ImproperlyConfigured(
                    "%s has no 'get_ajax_add_url' method, (required t add new models with selectize widget)"
                    % model_admin.__class__.__name__
                )

            add_url = model_admin.get_ajax_add_url()
        else:
            raise ImproperlyConfigured(
                "%s is not register in the admin, (required to add new models with selectize widget)" % add_to.__name__
            )

        if add_to and add_url:
            create = u"""
                create: function(input) {
                    var csrf_token = $(":input[name='csrfmiddlewaretoken']").val();
                    $.ajax({
                        url: "%(url)s",
                        type: 'POST',
                        dataType: 'json',
                        data: {
                            input: input,
                            csrfmiddlewaretoken: csrf_token
                        },
                        error: function() {
                            alert("%(error_msg)s");
                        },
                        success: function(res) {
                            var control = $("#%(id)s")[0].selectize;
                            control.addOption(res);
                            control.setValue(res.value);
                        }
                    });

                    return false;
                }
            """ % {
                'id': attrs['id'],
                'url': add_url,
                'error_msg': 'Ups, something went wrong, could not add item.',
            }
        else:
            create = ""

        if "__prefix__" in name:
            script = ""
        else:
            script = u"""
                <script type="text/javascript">
                    $(document).ready(function() {
                        $("#%(id)s").selectize({
                            plugins: ['remove_button', ], //  'drag_drop' 'restore_on_backspace'
                            sortField: 'text',
                            %(create)s
                        });
                    });
                </script>
            """ % {
                'id': attrs['id'],
                'create': create,
            }

        return format_html(u'{0}\n{1}', output, mark_safe(script))


class VisibilityWidget(forms.CheckboxInput):
    def render(self, name, value, attrs=None, renderer=None):
        widget_render = render_to_string('admin/visibility-widget.html')
        output = super().render(name, value, attrs=attrs)
        return output + widget_render

    @property
    def media(self):
        js = [
            "admin/js/visibility-widget.js",
        ]

        return forms.Media(js=js)


class FeaturedWidget(forms.CheckboxInput):
    def render(self, name, value, attrs=None, renderer=None):
        widget_render = render_to_string('admin/widgets/property-featured-widget.html')
        output = super(FeaturedWidget, self).render(name, value, attrs=attrs)
        return output + widget_render

    @property
    def media(self):
        js = [
            "admin/js/property-featured-widget.js",
        ]

        return forms.Media(js=js)


class LocationBaseWidget(Select):
    @property
    def media(self):
        js = ["admin/js/selectize.min.js"]
        css = ["admin/css/selectize.theme.css"]
        return forms.Media(
            js=[static("%s" % path) for path in js], css={"screen": [static("%s" % path) for path in css]}
        )

    def get_autocomplete_url(self):
        return ''

    def get_add_url(self):
        return ''

    def render_options(self, choices, selected_choices):
        # Normalize to strings.
        selected_choices = set(force_str(v) for v in selected_choices)
        output = []
        for option_value, option_label in chain(self.choices, choices):
            if option_value is None:
                option_value = ''
            option_value = force_str(option_value)
            if option_value not in selected_choices:
                continue
            output.append(self.render_option(selected_choices, option_value, option_label))

        return '\n'.join(output)

    def render(self, name, value, attrs=None, renderer=None):
        # if value is not None and not isinstance(value, six.string_types):
        #    value = edit_string_for_tags([o.tag for o in value.select_related("tag")])

        if "placeholder" not in attrs:
            attrs['placeholder'] = 'e.g.: Lisbon ...'

        output = super(LocationBaseWidget, self).render(name, value, attrs)

        url = self.get_autocomplete_url()

        if url:
            autocomplete = u"""
            load: function(query, callback) {
                if (!query.length) return callback();
                $.ajax({
                    url: "%(url)s",
                    type: 'GET',
                    dataType: 'json',
                    cache: false,
                    data: {
                        term: query,
                    },
                    error: function() {
                        callback();
                    },
                    success: function(res) {
                        callback(res);
                    }
                });
            },
            """ % {
                'url': url
            }
        else:
            autocomplete = ""

        add_url = self.get_add_url()
        if add_url:
            field = 'name'
            create = u"""
            create: function(value, callback){
                locationObjectPopup("%(url)s?_popup=1&%(field)s="+value);
                callback();
            },
            """ % {
                'url': add_url,
                'field': field,
            }
        else:
            create = ""

        script = u"""
            <script type="text/javascript">
                window.dismissAddRelatedObjectPopup = function(win, newId, newRepr) {
                    var instance = $("#"+win.name)[0].selectize;
                    var id = html_unescape(newId);
                    var name = html_unescape(newRepr);
                    instance.addOption({
                        'pk': id,
                        'name': name
                    });
                    instance.addItem(id);
                    instance.blur();
                    win.close();
                }
                $(document).ready(function() {

                    function locationObjectPopup(href) {
                        var win = window.open(href, '%(id)s', 'height=500,width=800,resizable=yes,scrollbars=yes');
                        win.focus();
                        return false;
                    }

                    $("#%(id)s").selectize({
                        valueField: 'pk',
                        labelField: 'name',
                        searchField: ['name', 'city', 'country', 'region', 'district'],
                        persist: false,
                        closeAfterSelect: true,
                        %(create)s
                        %(autocomplete)s
                        render: {
                            option: function(item, escape) {
                                var city = item.city;
                                var country = item.country;
                                var region = item.region;
                                var district = item.district;
                                return '<div>' +
                                    escape(item.name) +
                                    (city ? ' <span class="label label-primary">' + escape(city) + '</span>' : '') +
                                    (district ? ' <span class="label label-default">' + escape(district) + '</span>' : '') +
                                    (region ? ' <span class="label label-default">' + escape(region) + '</span>' : '') +
                                    (country ? ' <span class="label label-success">' + escape(country) + '</span>' : '') +
                                '</div>';
                            }
                        },
                    });
                });
            </script>
        """ % {
            'id': attrs['id'],
            'autocomplete': autocomplete,
            'create': create,
        }

        return format_html(u'{0}\n{1}', output, mark_safe(script))


class LocationWidget(LocationBaseWidget):
    def get_autocomplete_url(self):
        return ''

    def get_add_url(self):
        return ''

    def render(self, name, value, attrs=None, renderer=None):
        # if value is not None and not isinstance(value, six.string_types):
        #    value = edit_string_for_tags([o.tag for o in value.select_related("tag")])

        if "data-location-widget" not in attrs:
            attrs['data-id-location-widget'] = attrs['id']

        return super(LocationWidget, self).render(name, value, attrs)

    def render_option(self, selected_choices, option_value, option_label):
        if option_value is None:
            option_value = ''
        option_value = force_str(option_value)

        if not option_value:
            return ''
        try:
            location = Location.objects.get(pk=option_value)

            c = dict()
            if location.cities.first():
                c["city"] = location.cities.first().name
            if location.region:
                c["region"] = location.region.name
            if location.district:
                c["district"] = location.district.name
            if location.country:
                c["country"] = location.country.name

            data = escape(json.dumps(c))
        except Location.DoesNotExist:
            data = ""

        if option_value in selected_choices:
            selected_html = mark_safe(' selected="selected"')
            if not self.allow_multiple_selected:
                # Only allow for a single selection.
                selected_choices.remove(option_value)
        else:
            selected_html = ''

        option_format = """
            <option data-data="%(data)s" value="%(value)s"%(selected)s>%(label)s</option>
        """ % {
            'data': data,
            'value': option_value,
            'selected': selected_html,
            'label': force_str(option_label),
        }

        return mark_safe(option_format)


class PointWidget(BaseGeometryWidget):
    template_name = 'admin/point_widget.html'

    class Media:
        js = ('https://maps.google.com/maps/api/js',)  # ?sensor=false
        if hasattr(settings, 'GOOGLE_MAPS_API_KEY'):
            js = ("https://maps.google.com/maps/api/js?key=%s" % settings.GOOGLE_MAPS_API_KEY,)

        js += (
            # 'https://maps.google.com/maps/api/js?sensor=false',
            'js/wicket.js',
            'js/wicket-gmap3.js',
            'admin/js/point-widget.js',
        )


class Many2ManyWidget(forms.CheckboxSelectMultiple):
    def __init__(
        self, url, verbose_name=None, template='admin/many2many_select_widget.html', layout='table', *args, **kwargs
    ):
        self.request_url = url
        self.verbose_name = verbose_name
        self.template = template
        self.layout = layout
        super(Many2ManyWidget, self).__init__(*args, **kwargs)

    @property
    def media(self):
        js = [
            "js/jquery.min.js",
            "js/jquery-ui.js",
            "js/underscore-min.js",
            "js/backbone-min.js",
        ]

        css = {
            "screen": ["admin/css/m2m-ajax-widget.css"],
        }
        return forms.Media(js=js, css=css)

    def render(self, name, value, attrs=None, choices=(), renderer=None):
        if value is None:
            value = []
        final_attrs = self.build_attrs(attrs)
        # Normalize to strings
        str_values = [force_str(v) for v in value]
        str_values = ",".join(str_values)
        output = format_html(u'<input type="hidden" {0} value="{1}">', flatatt(final_attrs), str_values)

        context = {
            'output': output,
            'name': name,
            'request_url': self.request_url,
            'verbose_name': self.verbose_name,
            'layout': self.layout,
            'add_to': 'Add %s' % self.verbose_name,
            'search_for': 'Search for %s' % self.verbose_name,
            'use_the': 'Use the <b>Add %s</b> button to add %s to this item.' % (self.verbose_name, self.verbose_name),
        }

        html = render_to_string(self.template, context)
        return mark_safe(html)

    def value_from_datadict(self, data, files, name):
        value = data.get(name, None)
        if isinstance(value, six.string_types):
            return [v for v in value.split(',') if v]
        return value


class PropertiesMany2ManyWidget(Many2ManyWidget):
    def __init__(
        self,
        url='admin:%s_%s_propertiesajax' % (Property._meta.app_label, Property._meta.model_name),
        verbose_name=None,
        template='admin/widgets/many2many_properties_select_widget.html',
        layout='table',
        *args,
        **kwargs,
    ):
        super(PropertiesMany2ManyWidget, self).__init__(
            url, verbose_name=verbose_name, template=template, layout=layout, *args, **kwargs
        )

    @property
    def media(self):
        js = [
            "js/jquery.min.js",
            "js/underscore-min.js",
            "js/backbone-min.js",
        ]

        css = {
            "screen": ["admin/css/m2m-ajax-widget.css", "admin/css/m2m-properties-ajax-widget.css"],
        }
        return forms.Media(js=js, css=css)


class DecimalWithDropdownWidget(forms.MultiWidget):
    template_name = 'admin/widgets/decimal_with_dropdown_widget.html'

    def decompress(self, value):
        try:
            if isinstance(value, (list, tuple)):
                if value[0] in (None, ''):
                    return None, None
            if value:
                clean_value = json.loads(value.replace("'", '"'))
                return [clean_value['value'], clean_value['value_type']]
        except (IndexError, ValueError, TypeError):
            pass
        return None, None


class CustomMceEditorWidget(TinyMceEditorWidget):
    @property
    def media(self):
        return forms.Media(
            js=(
                'tinymce/tinymce.min.js',
                'admin/js/tinymce.init.js',
            ),
        )
