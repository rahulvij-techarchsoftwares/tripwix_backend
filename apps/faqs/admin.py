# apps/faq/admin.py

from django import forms
from django.contrib import admin
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.widgets import RichTextEditorWidget

from .models import FAQ, FAQCategory


class FAQForm(forms.ModelForm):
    class Meta:
        model = FAQ
        fields = ('question', 'answer', 'item_order')
        widgets = {
            'answer': RichTextEditorWidget(),
        }


class FAQInline(admin.TabularInline):
    model = FAQ
    form = FAQForm
    extra = 1
    fields = ('question', 'answer', 'item_order')
    ordering = ('item_order',)
    show_change_link = True


@admin.register(FAQCategory)
class FAQCategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('name',)}
    fieldsets = (
        (None, {'fields': ('name', 'slug'), 'description': _('Give your FAQ category a name.')}),
        (
            _('Visibility'),
            {
                'classes': ('collapse',),
                'fields': ('is_active',),
                'description': _('Control whether this FAQ category is active.'),
            },
        ),
    )
    list_display = ('name', 'slug', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'slug')
    inlines = [FAQInline]
