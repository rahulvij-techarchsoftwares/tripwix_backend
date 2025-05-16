from copy import deepcopy

from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.admin.options import BaseModelAdmin, InlineModelAdmin
from django.contrib.admin.sites import AdminSite
from django.core.exceptions import ImproperlyConfigured
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django_otp import user_has_device
from django_otp.forms import OTPAuthenticationFormMixin

from .utils import build_localized_fieldname, get_available_languages
from .views import AppsAutocompleteJsonView, OtpSetupView


class CoreAdminAuthenticationForm(AdminAuthenticationForm, OTPAuthenticationFormMixin):
    otp_device = forms.CharField(required=False, widget=forms.Select)
    otp_token = forms.CharField(required=False)

    # This is a placeholder field that allows us to detect when the user clicks
    # the otp_challenge submit button.
    otp_challenge = forms.CharField(required=False)

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.has_otp_device = False
        self.auth_two_factor_method = getattr(settings, 'ADMIN_TWO_FACTOR_METHOD', None)

    def clean(self):
        self.cleaned_data = super().clean()
        user = self.get_user()
        if user:
            self.has_otp_device = user_has_device(user)
        if self.auth_two_factor_method == 'strict' or self.has_otp_device:
            self.clean_otp(user)

        return self.cleaned_data


class CoreAdminSite(AdminSite):
    def get_urls(self):
        from django.urls import path

        urls = [
            path("apps-autocomplete/", self.apps_autocomplete_view, name="apps-autocomplete"),
        ]
        return urls + super().get_urls()

    def apps_autocomplete_view(self, request):
        return AppsAutocompleteJsonView.as_view(admin_site=self)(request)


class SecureAdminSite(CoreAdminSite):
    login_template = 'admin/two_factor_login.html'
    login_form = CoreAdminAuthenticationForm

    def has_permission(self, request):
        """
        Return True if the given HttpRequest has permission to view
        *at least one* page in the admin site.
        """
        user_has_permission = super().has_permission(request)
        if user_has_permission and getattr(settings, 'ADMIN_TWO_FACTOR_METHOD', None) == "strict":
            return request.user.is_verified()
        return user_has_permission

    def get_urls(self):
        from django.urls import path

        urls = [
            path("otp-setup/", self.otp_setup_view, name="opt-setup"),
        ]
        return urls + super().get_urls()

    @method_decorator(never_cache)
    def otp_setup_view(self, request, extra_context=None):
        if request.method == "GET" and self.has_permission(request):
            # Already logged-in, redirect to admin index
            index_path = reverse("admin:index", current_app=self.name)
            return HttpResponseRedirect(index_path)

        context = {
            **self.each_context(request),
            "title": _("OTP setup"),
            "subtitle": None,
            "app_path": request.get_full_path(),
            "username": request.user.get_username(),
        }

        defaults = {"extra_context": context}
        request.current_app = self.name
        return OtpSetupView.as_view(**defaults)(request)


class ReadOnlyInlineMixin(InlineModelAdmin):
    extra = 0

    # This disable add functionality
    def has_add_permission(self, *args, **kwargs):
        return True

    # This will disable delete functionality
    def has_delete_permission(self, *args, **kwargs):
        return False

    # This will disable change functionality
    def has_change_permission(self, *args, **kwargs):
        return False

    # Set all fields readonly
    def get_readonly_fields(self, *args, **kwargs):
        return [f.name for f in self.model._meta.fields] + self.fields


"""
class CustomTranslationAdmin(TranslationAdmin):
    def get_search_fields(self, request):
        default_language = mt_settings.DEFAULT_LANGUAGE
        trans_fields = self.trans_opts.get_field_names()
        new_search_fields = []
        for field_name in self.search_fields:
            lookups = field_name.split('__')
            if lookups[:1]:
                if lookups[:1][0] in trans_fields:
                    new_field = [f"{lookups[:1][0]}_{default_language}"] + lookups[1:]
                    new_search_fields.append('__'.join(new_field))
        new_search_fields = new_search_fields + list(self.search_fields)
        return new_search_fields
"""


class SelectizeWidgetLoadModelAdmin(admin.ModelAdmin):
    selectize_load_field_name = None

    def get_selectize_ajax_load_url(self):
        from django.urls import reverse

        info = self.model._meta.app_label, self.model._meta.model_name
        return reverse("admin:%s_%s_ajax_load" % info)

    def get_urls(self):
        from django.urls import path

        info = self.model._meta.app_label, self.model._meta.model_name
        urls = super(SelectizeWidgetLoadModelAdmin, self).get_urls()
        my_urls = [
            path(
                'selectize/ajax/load/',
                self.admin_site.admin_view(self.ajax_selectize_load_view, cacheable=False),
                name="%s_%s_ajax_load" % info,
            ),
        ]
        return my_urls + urls

    def ajax_selectize_query(self, request):
        return {}

    def ajax_selectize_result_output(self, result, request=None):
        return {'value': result.pk, 'text': "%s" % result}

    def ajax_selectize_load_view(self, request):
        if self.selectize_load_field_name is None:
            raise ImproperlyConfigured(
                '%s: missing selectize_load_field_name for SelectizeWidget' % self.__class__.__name__
            )

        if request.method == "GET" and request.is_ajax():
            query = self.ajax_selectize_query(request)
            query["{}__icontains".format(self.selectize_load_field_name)] = request.GET.get("term")
            results = list()
            for result in self.model.objects.filter(**query):
                results.append(self.ajax_selectize_result_output(result, request=request))
            return JsonResponse(results, safe=False)

        raise Http404()


class TranslationBaseModelAdmin(BaseModelAdmin):
    def __init__(self, *args, **kwargs):
        from modeltrans.translator import get_i18n_field

        super().__init__(*args, **kwargs)

        i18n_field = get_i18n_field(self.model)
        if i18n_field is not None:
            self.trans_opts = {
                'i18n': i18n_field,
                'field_names': [f.name for f in i18n_field.get_translated_fields() if not f.name.endswith('i18n')],
                'fields': i18n_field.fields,
            }
        else:
            self.trans_opts = None
        self._patch_prepopulated_fields()

    def _patch_prepopulated_fields(self):
        def localize(sources, lang):
            def append_lang(source):
                if self.trans_opts and source in self.trans_opts['fields']:
                    return build_localized_fieldname(source, lang)
                return source

            return tuple(map(append_lang, sources))

        prepopulated_fields = {}
        for dest, sources in self.prepopulated_fields.items():
            if dest in self.trans_opts['fields']:
                for lang in get_available_languages():
                    key = build_localized_fieldname(dest, lang)
                    prepopulated_fields[key] = localize(sources, lang)
            else:
                lang = settings.LANGUAGE_CODE
                prepopulated_fields[dest] = localize(sources, lang)

        self.prepopulated_fields = prepopulated_fields

    def replace_orig_field(self, option):
        if self.trans_opts is None:
            return options

        if option:
            option_new = list(option)
            for opt in option:
                if opt in self.trans_opts['fields']:
                    index = option_new.index(opt)
                    opt_fields = [
                        field_name for field_name in self.trans_opts['field_names'] if field_name.startswith(opt)
                    ]
                    option_new[index : index + 1] = opt_fields
                elif isinstance(opt, (tuple, list)) and ([o for o in opt if o in self.trans_opts['fields']]):
                    index = option_new.index(opt)
                    option_new[index : index + 1] = self.replace_orig_field(opt)
            option = option_new
        return option

    def _patch_fieldsets(self, fieldsets):
        if fieldsets:
            fieldsets_new = list(fieldsets)
            for name, dct in fieldsets:
                if 'fields' in dct:
                    dct['fields'] = self.replace_orig_field(dct['fields'])
            fieldsets = fieldsets_new
        return fieldsets

    def _get_declared_fieldsets(self, request, obj=None):
        # Take custom modelform fields option into account
        if not self.fields and hasattr(self.form, '_meta') and self.form._meta.fields:
            self.fields = self.form._meta.fields
        # takes into account non-standard add_fieldsets attribute used by UserAdmin
        fieldsets = self.add_fieldsets if getattr(self, 'add_fieldsets', None) and obj is None else self.fieldsets
        if fieldsets:
            return self._patch_fieldsets(fieldsets)
        elif self.fields:
            return [(None, {'fields': self.replace_orig_field(self.get_fields(request, obj))})]
        return None

    def _get_fieldsets_pre_form_or_formset(self, request, obj=None):
        return self._get_declared_fieldsets(request, obj)

    def _get_fieldsets_post_form_or_formset(self, request, form, obj=None):
        if self.fields is None:
            return [(None, {"fields": self.get_fields(request, obj)})]
        base_fields = self.replace_orig_field(form.base_fields.keys())
        fields = list(base_fields) + list(self.get_readonly_fields(request, obj))
        return [(None, {'fields': self.replace_orig_field(fields)})]

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        self.patch_translation_field(db_field, field, request, **kwargs)
        return field

    def _get_widget_from_field(self, field):
        # retrieve "nested" widget in case of related field
        if isinstance(field.widget, admin.widgets.RelatedFieldWidgetWrapper):
            return field.widget.widget
        else:
            return field.widget

    def patch_translation_field(self, db_field, field, request, **kwargs):
        from apps.core.utils import build_css_class

        if self.trans_opts and db_field.name in self.trans_opts['field_names']:
            orig_formfield = self.formfield_for_dbfield(db_field.original_field, request, **kwargs)
            field.widget = deepcopy(orig_formfield.widget)

            # if any widget attrs are defined on the form they should be copied
            try:
                field.widget = deepcopy(self.form._meta.widgets[db_field.original_field.name])  # this is a class
                if isinstance(field.widget, type):  # if not initialized
                    field.widget = field.widget(attrs)  # initialize form widget with attrs
            except (AttributeError, TypeError, KeyError):
                pass

            attrs = field.widget.attrs
            css_classes = self._get_widget_from_field(field).attrs.get('class', '').split(' ')
            css_classes.append('mt')
            # Add localized fieldname css class
            css_classes.append(build_css_class(db_field.name, 'mt-field'))
            if db_field.language == settings.LANGUAGE_CODE:
                css_classes.append('mt-default')

                if orig_formfield.required:
                    field.required = True
                    field.blank = False

            self._get_widget_from_field(field).attrs['class'] = ' '.join(css_classes)

    def get_exclude(self, request, obj=None):
        # use default implementation for models without i18n-field
        if self.trans_opts is None:
            return super().get_exclude(request)

        excludes = []
        for field_name in self.trans_opts['fields']:
            excludes.append(field_name)

        for field in self.trans_opts['i18n'].get_translated_fields():
            if field.language is None:
                excludes.append(field.name)

        # de-duplicate
        return list(set(excludes))

    def get_readonly_fields(self, request, obj=None):
        return self.replace_orig_field(self.readonly_fields)


class TranslationAdmin(TranslationBaseModelAdmin, admin.ModelAdmin):
    def get_fieldsets(self, request, obj=None):
        return self._get_fieldsets_pre_form_or_formset(request, obj) or self._get_fieldsets_post_form_or_formset(
            request, self.get_form(request, obj, fields=None), obj
        )


class TranslationInlineModelAdmin(TranslationBaseModelAdmin, InlineModelAdmin):
    def get_fieldsets(self, request, obj=None):
        # FIXME: If fieldsets are declared on an inline some kind of ghost
        # fieldset line with just the original model verbose_name of the model
        # is displayed above the new fieldsets.
        declared_fieldsets = self._get_fieldsets_pre_form_or_formset(request, obj)
        if declared_fieldsets:
            return declared_fieldsets
        form = self.get_formset(request, obj, fields=None).form
        return self._get_fieldsets_post_form_or_formset(request, form, obj)


class TranslationTabularInline(TranslationInlineModelAdmin, admin.TabularInline):
    pass


class TranslationStackedInline(TranslationInlineModelAdmin, admin.StackedInline):
    pass
