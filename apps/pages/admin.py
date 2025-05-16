from django.conf import settings
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from apps.components.admin import CollectionAdmin
from apps.components.forms import CollectionAdminForm
from apps.core.admin import TranslationAdmin
from apps.core.utils import get_translation_fields
from apps.core.widgets import SlugWidget, VisibilityWidget

from .models import Page


class PageAdminForm(CollectionAdminForm):
    def __init__(self, *args, **kwargs):
        super(PageAdminForm, self).__init__(*args, **kwargs)

        for field in get_translation_fields('slug'):
            lang = field.replace('slug_', '')
            self.fields[field].widget = SlugWidget(model=Page, lang=lang, attrs={'class': f'mt mt-field-slug-{lang}'})

    class Meta:
        model = Page
        fields = '__all__'
        widgets = {
            'slug': SlugWidget(model=Page),
            'is_active': VisibilityWidget,
        }


@admin.register(Page)
class PageAdmin(CollectionAdmin, TranslationAdmin):
    search_fields = ['title', 'slug']
    prepopulated_fields = {'slug': ('title',)}
    selectize_load_field_name = 'title'
    list_display = ('__str__', 'slug', 'get_collection_type', 'is_active')
    form = PageAdminForm

    fieldsets = (
        (
            None,
            {
                'fields': (
                    'title',
                    'get_collection_type',
                ),
            },
        ),
        (
            _('Media'),
            {
                'fields': ('video',),
                'description': _('Upload a video file for this page.'),
            },
        ),
        (
            _('Search Engine'),
            {
                'classes': (
                    'collapse',
                    'collapsable',
                ),
                'fields': (
                    'slug',
                    'seo_title',
                    'seo_description',
                    'seo_image',
                ),
                'description': _(
                    'Set up the title, meta description, and handle. These help define how this object shows up on search engines.'
                ),
            },
        ),
        (
            _('Visibility'),
            {
                'fields': (
                    'is_active',
                    'publication_date',
                ),
                'description': _('Control whether this can be seen on your frontend.'),
            },
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                'fields': ('title', 'collection_type', 'video'),
            },
        ),
        (
            _('Search Engine'),
            {
                'fields': (
                    'slug',
                    'seo_title',
                    'seo_description',
                    'seo_image',
                ),
                'description': _(
                    'Set up the title, meta description, and handle. These help define how this object shows up on search engines.'
                ),
            },
        ),
    )

    change_form_template = 'admin/page_change_form.html'

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['frontend_url'] = settings.FRONTOFFICE_URL
        return super().change_view(request, object_id, form_url, extra_context)
