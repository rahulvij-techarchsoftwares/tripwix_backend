from django.contrib import admin

from apps.core.admin import TranslationAdmin, TranslationTabularInline

from .models import ComponentForm, ComponentFormFields


class ComponentFormFieldsInlineAdmin(TranslationTabularInline):
    model = ComponentFormFields
    prepopulated_fields = {'slug': ('name',)}
    autocomplete_fields = ('field',)
    extra = 1


@admin.register(ComponentForm)
class ComponentFormAdmin(admin.ModelAdmin):
    inlines = [ComponentFormFieldsInlineAdmin]
    prepopulated_fields = {'slug': ('title',)}

    list_display = (
        'title',
        'slug',
        'is_active',
    )
    search_fields = ('title', 'slug')

    fieldsets = (
        (
            None,
            {
                'fields': (
                    'title',
                    'slug',
                    'is_active',
                )
            },
        ),
    )
