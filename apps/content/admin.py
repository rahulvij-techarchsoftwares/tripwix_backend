from django.contrib import admin
from django.db import models
from django.utils.translation import gettext_lazy as _
from import_export.admin import ImportExportModelAdmin

from apps.core.admin import TranslationAdmin
from apps.core.utils import ValidContentTypes
from apps.core.widgets import RichTextEditorWidget

from .forms import ContentAdminForm
from .models import Content


@admin.register(Content)
class ContentAdmin(TranslationAdmin, ImportExportModelAdmin):
    form = ContentAdminForm

    SETTINGS_FIELD = (
        'settings',
        {
            'classes': (
                'collapse',
                'collapsable',
            ),
            'fields': ('unique_name',),
            'description': _('Manage the settings for this content.'),
        },
    )

    add_fieldsets = (
        (
            None,
            {
                'fields': (
                    'title',
                    'content_type',
                    'unique_name',
                ),
                'description': _('Manage the settings for this content.'),
            },
        ),
    )
    app_fieldsets = (
        (
            None,
            {
                'fields': (
                    'title',
                    'app_model',
                    'object_id',
                    'content_object',
                ),
                'description': _('Write the title and select a object.'),
            },
        ),
        SETTINGS_FIELD,
    )
    image_fieldsets = (
        (
            None,
            {
                'fields': (
                    'title',
                    'image',
                ),
                'description': _('Write the title and upload an image.'),
            },
        ),
        SETTINGS_FIELD,
    )
    fieldsets = (
        (
            None,
            {
                'fields': (
                    'title',
                    'content_text',
                ),
                'description': _('Write the title and text for this content.'),
            },
        ),
        SETTINGS_FIELD,
    )

    list_display = ('unique_name', 'title', 'get_content_type')
    search_fields = ('unique_name', 'title')
    prepopulated_fields = {"unique_name": ("title",)}

    formfield_overrides = {
        models.TextField: {'widget': RichTextEditorWidget},
    }

    def get_content_type(self, obj):
        return obj.content_type_display()

    get_content_type.short_description = _('Type')

    def render_change_form(self, request, context, *args, **kwargs):
        if 'app_model' in context['adminform'].form.fields:
            context['adminform'].form.fields['app_model'].queryset = ValidContentTypes(
                ignore_list=[
                    Content,
                ]
            )
        return super().render_change_form(request, context, *args, **kwargs)

    # TODO: find a way to autocomplete the app model relation fields
    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return self._patch_fieldsets(self.add_fieldsets)
        if obj.content_type == Content.Types.APP:
            return self._patch_fieldsets(self.app_fieldsets)
        if obj.content_type == Content.Types.IMAGE:
            return self._patch_fieldsets(self.image_fieldsets)
        return self._patch_fieldsets(self.fieldsets)
