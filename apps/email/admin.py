from collections import OrderedDict
from functools import update_wrapper

from django.conf import settings
from django.contrib import admin
from django.contrib.admin.utils import flatten_fieldsets, unquote
from django.contrib.sites.models import Site
from django.core.exceptions import PermissionDenied
from django.forms import modelform_factory
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import translation
from django.utils.module_loading import import_string
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

# from apps.core.admin import ActionModelAdmin, ActionItem
from apps.core.utils import domain_with_proto
from apps.email import definitions
from apps.email.models import EmailDefinitionModel, EmailDefinitionTranslationModel
from contrib.admin_relation import (
    RelationAdmin,
    RelationAdminHelper,
    RelationAdminMixin,
    RootRelationAdmin,
    csrf_protect_m,
)


class EmailDefinitionTranslationAdmin(RelationAdmin):
    model = EmailDefinitionTranslationModel  # required for relation admin

    list_display = (
        'lang',
        'is_active',
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def get_fieldsets(self, request, obj=None):
        email_def_form = import_string(obj.email_definition.module_path)
        form_fields = email_def_form.declared_fields.keys()
        if form_fields:
            return [
                (None, {'fields': form_fields}),
                (
                    None,
                    {
                        'fields': [
                            'is_active',
                        ]
                    },
                ),
            ]
        return []

    def get_form(self, request, obj=None, change=False, **kwargs):
        if 'fields' in kwargs:
            fields = kwargs.pop('fields')
        else:
            fields = flatten_fieldsets(self.get_fieldsets(request, obj))
        readonly_fields = self.get_readonly_fields(request, obj)

        email_def_form = import_string(obj.email_definition.module_path)
        # Remove declared form fields which are in readonly_fields.
        new_attrs = OrderedDict.fromkeys(f for f in readonly_fields if f in self.form.declared_fields)
        form = type(
            self.form.__name__,
            (
                email_def_form,
                self.form,
            ),
            new_attrs,
        )

        defaults = {
            'form': form,
            'fields': fields,
            **kwargs,
        }

        return modelform_factory(self.model, **defaults)

    def save_form(self, request, form, change):
        instance = form.save(commit=False)
        instance.data = form.save_data()
        return instance

    @csrf_protect_m
    def changelist_view(self, request, *args, **kwargs):
        extra_context = kwargs.get('extra_context')
        request.relation_admin = RelationAdminHelper(self, request, args)
        extra_context = self.context_add_parent_data(request, extra_context)
        languages = settings.LANGUAGES
        existing_definition_languages = set()

        for email_definition_obj in self.get_queryset(request):
            if email_definition_obj.lang in [lang_code for lang_code, _l in languages]:
                existing_definition_languages.add(email_definition_obj.lang)

        for lang_code, _l in languages:
            if lang_code in existing_definition_languages:
                continue

            EmailDefinitionTranslationModel.objects.create(
                email_definition=request.relation_admin.parent_instance,
                lang=lang_code,
                data=request.relation_admin.parent_instance.data,
            )
        return super(RelationAdminMixin, self).changelist_view(request, extra_context)


@admin.register(EmailDefinitionModel)
class EmailDefinitionModelAdmin(RootRelationAdmin):
    list_display = ('__str__', 'allow_send', 'get_translations', 'preview_url')
    relation_admins = [
        EmailDefinitionTranslationAdmin,
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def get_translations(self, obj):
        return obj.translations.filter(is_active=True).count()

    get_translations.short_description = _('Active Translations')

    def get_urls(self):
        def wrap(view):
            def wrapper(*args, **kwargs):
                return self.admin_site.admin_view(view)(*args, **kwargs)

            wrapper.model_admin = self
            return update_wrapper(wrapper, view)

        info = self.model._meta.app_label, self.model._meta.model_name

        urlpatterns = [
            path('<path:object_id>/preview/', wrap(self.preview_view), name='%s_%s_preview' % info),
        ]
        return urlpatterns + super().get_urls()

    def preview_view(self, request, object_id):
        model = self.model
        opts = model._meta

        obj = self.get_object(request, unquote(object_id))

        if not self.has_view_or_change_permission(request, obj):
            raise PermissionDenied

        if obj is None:
            return self._get_obj_does_not_exist_redirect(request, opts, object_id)

        email_definition = import_string(obj.module_path)

        sample_bank = {}
        context = email_definition.sample_context(sample_bank)
        # DEFAULT GLOBAL CONTEXT
        email_context = {
            'proto_and_domain': domain_with_proto(),
            'site': Site.objects.get_current(),
        }
        email_context.update(context)

        lang = request.GET.get('lang', translation.get_language())
        email = email_definition(context=email_context, lang=lang)

        if 'html_only' in request.GET:
            return HttpResponse(email.get_html_content())

        user = request.user
        from_email = getattr(settings, 'EMAIL', {}).get('from_email', 'no-reply@example.com')
        to_email = user.email if user.email else 'user@example.com'

        context = {
            **self.admin_site.each_context(request),
            'title': _('Email Preview: %s') % obj,
            'opts': opts,
            'object_id': object_id,
            'original': obj,
            'media': self.media,
            'subject': email.get_subject(),
            'text_content': email.get_text_content(),
            'html_content': email.get_html_content(),
            'from_email': from_email,
            'to_email': to_email,
            'languages': settings.LANGUAGES,
            'lang': lang,
        }

        return TemplateResponse(request, 'admin/email_preview.html', context)

    def preview_url(self, obj):
        info = self.model._meta.app_label, self.model._meta.model_name
        url = reverse('admin:%s_%s_preview' % info, kwargs={'object_id': obj.id})
        return mark_safe(f'<a href="{url}" >preview email</a>')

    preview_url.short_description = ''

    def get_fieldsets(self, request, obj=None):
        email_def_form = import_string(obj.module_path)
        form_fields = email_def_form.declared_fields.keys()
        if form_fields:
            return [
                (None, {'fields': form_fields}),
                (None, {'fields': ('allow_send',)}),
            ]
        return [
            (None, {'fields': ('allow_send',)}),
        ]

    def get_form(self, request, obj=None, change=False, **kwargs):
        if 'fields' in kwargs:
            fields = kwargs.pop('fields')
        else:
            fields = flatten_fieldsets(self.get_fieldsets(request, obj))
        readonly_fields = self.get_readonly_fields(request, obj)

        email_def_form = import_string(obj.module_path)
        # Remove declared form fields which are in readonly_fields.
        new_attrs = OrderedDict.fromkeys(f for f in readonly_fields if f in self.form.declared_fields)
        form = type(
            self.form.__name__,
            (
                email_def_form,
                self.form,
            ),
            new_attrs,
        )

        defaults = {
            'form': form,
            'fields': fields,
            **kwargs,
        }

        return modelform_factory(self.model, **defaults)

    def save_form(self, request, form, change):
        instance = form.save(commit=False)
        instance.data = form.save_data()
        return instance

    def changelist_view(self, request, extra_context=None):
        all_definitions = definitions.all()
        existing_definitions = set()

        for email_definition_obj in self.get_queryset(request):
            if email_definition_obj.module_path in all_definitions:
                existing_definitions.add(email_definition_obj.module_path)

        for module_path, data in all_definitions.items():
            if module_path in existing_definitions:
                continue

            email_definition = import_string(module_path)
            EmailDefinitionModel.objects.create(
                name=data.get('name', email_definition.__name__), module_path=module_path
            )

        return super().changelist_view(request, extra_context=extra_context)
