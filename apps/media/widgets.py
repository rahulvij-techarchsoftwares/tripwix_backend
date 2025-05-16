from itertools import chain

import six
from django import forms
from django.contrib.admin.widgets import AdminFileWidget
from django.forms.widgets import CheckboxInput, FileInput, Select, TextInput
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.urls import reverse
from django.utils.encoding import force_str
from django.utils.html import conditional_escape, escape
from django.utils.safestring import mark_safe
from photologue.models import PhotoSize


class ImageWidget(AdminFileWidget):
    template_with_initial = u'<div style="position:relative;">%(initial)s%(clear_template)s<div class="image-widget-container">\
        <span>%(input_text)s:</span>%(input)s</div></div>'
    template_with_clear = u'<label for="%(clear_checkbox_id)s" class="clearable-file-input" \
        style="background-color:#e1e1e1; position:absolute; top:0px; left:0px; display:block; padding:5px 12px;">\
        %(clear)s %(clear_checkbox_label)s</label>'

    def render(self, name, value, **kwargs):
        substitutions = {
            'initial_text': self.initial_text,
            'input_text': self.input_text,
            'clear_template': '',
            'clear_checkbox_label': self.clear_checkbox_label,
        }
        template = u'%(input)s'
        substitutions['input'] = super(FileInput, self).render(name, value, **kwargs)

        if value and hasattr(value, "url"):
            template = self.template_with_initial
            substitutions['initial'] = (
                u'<a style="display:inline-block; padding:3px; background-color:#e1e1e1;" target="_blank" href="%s">\
                <img style="max-height:180px; max-width:100%%;" src="%s" alt="%s"/></a>'
                % (escape(value.url), escape(value.url), escape(force_str(value)))
            )
            if not self.is_required:
                checkbox_name = self.clear_checkbox_name(name)
                checkbox_id = self.clear_checkbox_id(checkbox_name)
                substitutions['clear_checkbox_name'] = conditional_escape(checkbox_name)
                substitutions['clear_checkbox_id'] = conditional_escape(checkbox_id)
                substitutions['clear'] = CheckboxInput().render(checkbox_name, False, attrs={'id': checkbox_id})
                substitutions['clear_template'] = self.template_with_clear % substitutions

        return mark_safe(template % substitutions)


class MediaPhotoWidget(TextInput):
    @property
    def media(self):
        js = [
            "js/jquery.min.js",
            "js/jquery.ui.widget.js",
            "js/tmpl.min.js",
            "js/load-image.all.min.js",
            "js/jquery.iframe-transport.js",
            "js/jquery.fileupload.js",
            "js/jquery.fileupload-process.js",
            "js/jquery.fileupload-image.js",
            "js/jquery.fileupload-validate.js",
            "js/jquery.fileupload-ui.js",
            "admin/js/jquery-sortable.js",
            "admin/js/media_widget.js",
        ]
        css = ["css/media_gallery.css", "css/jquery.fileupload-ui.css"]
        return forms.Media(
            js=[static("%s" % path) for path in js],
            css={"screen": [static("%s" % path) for path in css]},
        )

    def label_for_value(self, value):
        return ""

    def value_from_datadict(self, data, files, name):
        value = data.get(name)
        if value:
            return value.split(",")

    def render(self, name, value, attrs=None, choices=(), renderer=None):
        try:
            thumbnail = PhotoSize.objects.get(name="media_thumbnail")
        except:
            thumbnail = None

        if self.queryset and value:
            value = [int(x) for x in value]
            photos_query = self.queryset.filter(id__in=value)
            photos_list = list(photos_query)
            photos_list.sort(key=lambda photo: value.index(photo.id))
            photos = photos_list
        else:
            photos = None

        context = {"photos": photos}
        if thumbnail:
            context["max_thumb_width"] = thumbnail.width
            context["max_thumb_height"] = thumbnail.height
        else:
            context["max_thumb_width"] = 180
            context["max_thumb_height"] = 120

        info = self.to._meta.app_label, self.to._meta.model_name
        context["can_select"] = self.can_select
        context["upload_url"] = reverse("admin:%s_%s_upload" % info)
        context["photos_uri"] = reverse("admin:%s_%s_get_photos" % info)
        context["change_url"] = reverse("admin:%s_%s_changelist" % info)

        output = render_to_string("admin/media_photo_widget.html", context)

        if value:
            value = ",".join([force_str(v) for v in value])
        else:
            value = ""

        output += super(forms.TextInput, self).render(name, value, attrs)
        return mark_safe(output)


class SortedCheckboxSelectMultiple(forms.CheckboxSelectMultiple):
    class Media:
        js = (
            "js/force_jquery.js",
            "admin/js/jquery-sortable.js",
            "admin/js/sorted_select.js",
        )
        css = {"screen": ("admin/css/sorted_select.css",)}

    def build_attrs(self, attrs=None, **kwargs):
        attrs = super(SortedCheckboxSelectMultiple, self).build_attrs(attrs, **kwargs)
        classes = attrs.setdefault("class", "").split()
        classes.append("sortedm2m")
        attrs["class"] = " ".join(classes)
        return attrs

    def render(self, name, value, attrs=None, choices=()):
        if value is None:
            value = []
        has_id = attrs and "id" in attrs
        final_attrs = self.build_attrs(attrs, name=name)

        # Normalize to strings
        str_values = [force_str(v) for v in value]

        selected = []
        unselected = []

        for i, (option_value, option_label) in enumerate(chain(self.choices, choices)):
            if has_id:
                final_attrs = dict(final_attrs, id="%s_%s" % (attrs["id"], i))
                label_for = ' for="%s"' % conditional_escape(final_attrs["id"])
            else:
                label_for = ""

            cb = forms.CheckboxInput(final_attrs, check_test=lambda value: value in str_values)
            option_value = force_str(option_value)
            rendered_cb = cb.render(name, option_value)
            option_label = conditional_escape(force_str(option_label))
            item = {
                "label_for": label_for,
                "rendered_cb": rendered_cb,
                "option_label": option_label,
                "option_value": option_value,
            }
            if option_value in str_values:
                selected.append(item)
            else:
                unselected.append(item)

        ordered = []
        for value in str_values:
            for select in selected:
                if value == select["option_value"]:
                    ordered.append(select)
        selected = ordered

        html = render_to_string(
            "admin/sorted_checkbox_select_multiple_widget.html",
            {"selected": selected, "unselected": unselected},
        )
        return mark_safe(html)

    def value_from_datadict(self, data, files, name):
        value = data.get(name, None)
        if isinstance(value, six.string_types):
            return [v for v in value.split(",") if v]
        return value


class MediaPhotoFkWidget(TextInput):
    template_name = 'admin/media_photo_widget.html'
    max_files = 1

    def value_from_datadict(self, data, files, name):
        value = super().value_from_datadict(data, files, name)
        if not value:
            return ''

        try:
            value = int(value)
        except ValueError:
            value = int(value.split(',')[0])
        return value

    @property
    def media(self):
        return forms.Media(
            js=(
                'admin/js/force.jquery.js',
                'admin/js/dropzone-min.js',
                'admin/js/Sortable.min.js',
                'admin/js/media_photo_widget.js',
            ),
            css={'screen': ('admin/css/media_photo_widget.css',)},
        )

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)

        thumbnail = None

        if self.queryset and value:
            if isinstance(value, (int, str)):
                value = [
                    value,
                ]
            value = [int(x) for x in value]
            photos_query = self.queryset.filter(id__in=value)
            photos_list = list(photos_query)
            photos_list.sort(key=lambda photo: value.index(photo.id))
            photos = photos_list
        else:
            photos = None

        context['photos'] = photos

        if thumbnail:
            context['max_thumb_width'] = thumbnail.width
            context['max_thumb_height'] = thumbnail.height
        else:
            context['max_thumb_width'] = 280
            context['max_thumb_height'] = 'null'

        info = self.to._meta.app_label, self.to._meta.model_name
        if self.max_files:
            context['max_files'] = self.max_files
        context['can_select'] = self.can_select
        context['readonly'] = context.get('widget', dict()).get('attrs', dict()).get('readonly', False)
        context['upload_url'] = reverse("admin:%s_%s_upload" % info)
        context['change_url'] = reverse("admin:%s_%s_changelist" % info)
        context['photos_url'] = reverse("admin:%s_%s_get_photos" % info)
        context['photo_url'] = reverse("admin:%s_%s_get_photo" % info)

        return context


class MediaPhotoWidget(MediaPhotoFkWidget):
    max_files = None

    def format_value(self, value):
        if value == '' or value is None:
            return ''
        else:
            return ','.join([str(v) for v in value])

    def value_from_datadict(self, data, files, name):
        value = data.get(name)
        if value:
            return value.split(',')


class MediaPhotoForeignKeyWidget(Select):
    option_template_name = 'media/forms/widgets/select_option.html'

    @property
    def media(self):
        js = [
            "admin/js/image-picker.min.js",
            "admin/js/fk-image-picker.js",
        ]
        css = ["admin/css/image-picker.css"]
        return forms.Media(
            js=[static("%s" % path) for path in js], css={"screen": [static("%s" % path) for path in css]}
        )
