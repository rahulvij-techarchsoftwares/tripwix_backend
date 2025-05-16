from django.contrib import admin
from django.contrib.admin import helpers
from django.contrib.admin.utils import flatten_fieldsets, unquote
from django.core.exceptions import PermissionDenied
from django.template.defaultfilters import linebreaksbr
from django.utils.translation import gettext_lazy as _

from apps.core.admin import SelectizeWidgetLoadModelAdmin, TranslationAdmin, TranslationTabularInline
from apps.core.utils import ValidContentTypes, get_translation_fields

from . import choices
from .forms import CollectionAdminForm
from .models import (
    CollectionType,
    CollectionTypeComponents,
    Component,
    ComponentField,
    ComponentFieldOption,
    ComponentFields,
)
from .utils import get_component_fields_gen

IS_POPUP_VAR = '_popup'

from import_export.admin import ExportActionModelAdmin, ImportExportModelAdmin


class ComponentFieldOptionInlineAdmin(TranslationTabularInline):
    model = ComponentFieldOption
    prepopulated_fields = {'slug': ('name',)}
    extra = 2


@admin.register(ComponentField)
class ComponentFieldAdmin(TranslationAdmin):
    inlines = [ComponentFieldOptionInlineAdmin]
    list_display = (
        '__str__',
        'field_type',
    )
    search_fields = [
        'name',
    ]
    change_form_template = 'admin/component_field_change_form.html'

    def render_change_form(self, request, context, *args, **kwargs):
        if 'app_model' in context['adminform'].form.fields:
            context['adminform'].form.fields['app_model'].queryset = ValidContentTypes()
        return super().render_change_form(request, context, *args, **kwargs)


class ComponentFieldsInlineAdmin(TranslationTabularInline):
    model = ComponentFields
    prepopulated_fields = {'slug': ('name',)}
    autocomplete_fields = ('field',)
    extra = 1


@admin.register(Component)
class ComponentAdmin(TranslationAdmin, ImportExportModelAdmin, ExportActionModelAdmin):
    inlines = [ComponentFieldsInlineAdmin]
    prepopulated_fields = {'slug': ('name',)}


class CollectionTypeComponentsInlineAdmin(admin.TabularInline):
    model = CollectionTypeComponents
    extra = 1


@admin.register(CollectionType)
class CollectionTypeAdmin(TranslationAdmin):
    list_display = ('__str__', 'is_internal')
    inlines = [CollectionTypeComponentsInlineAdmin]
    prepopulated_fields = {'slug': ('name',)}


class CollectionAdmin(SelectizeWidgetLoadModelAdmin):
    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        field = super(CollectionAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == 'collection_type':
            if request.user.is_superuser:
                field.queryset = field.queryset.all()
            elif request.user.is_staff:
                field.queryset = field.queryset.filter(is_internal=False)
            else:
                field.queryset = field.queryset.none()
        return field

    def _get_declared_fieldsets(self, request, obj=None):
        if not obj:
            return self._patch_fieldsets(self.add_fieldsets)
        return self._patch_fieldsets(self.fieldsets)

    def get_collection_type(self, obj):
        return obj.collection_type

    get_collection_type.short_description = _("Collection type")

    def ajax_selectize_result_output(self, result, request=None):
        return {'value': result.pk, 'text': "%s" % result, "page_url": result.get_absolute_url()}

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ('get_collection_type', 'fields_data_json')
        return self.readonly_fields

    def get_component_fieldsets(self, request, obj=None):
        fieldsets = list(self.fieldsets)
        block_number = len(fieldsets) - 1
        prev_block_pk = None
        # appends model fields to the fieldset
        for field, field_name, component_field, component, block_pk in get_component_fields_gen(obj):
            if prev_block_pk != block_pk:
                block_number += 1
                prev_block_pk = block_pk
                # creates a fieldset block with the block name and fields
                fieldsets.append(
                    (
                        component.name,
                        {
                            'fields': [],
                            'description': linebreaksbr(component.description),
                            'classes': (
                                'collapse',
                                'collapsable',
                            ),
                        },
                    )
                )

            if component_field.is_translatable:
                for trans_field in get_translation_fields(field_name):
                    fieldsets[block_number][1]['fields'].append(trans_field)
                continue
            else:
                fieldsets[block_number][1]['fields'].append(field_name)

        return fieldsets

    def change_view(self, request, object_id, form_url='', extra_context=None):
        model = self.model
        opts = model._meta
        obj = self.get_object(request, unquote(object_id))

        if request.method == 'POST':
            if not self.has_change_permission(request, obj):
                raise PermissionDenied
        else:
            if not self.has_view_or_change_permission(request, obj):
                raise PermissionDenied

        if obj is None:
            return self._get_obj_does_not_exist_redirect(request, opts, object_id)

        fieldsets = self.get_fieldsets(request, obj)
        ModelForm = self.get_form(request, obj, change=True, fields=flatten_fieldsets(fieldsets))

        formsets = []
        if request.method == 'POST':
            form = ModelForm(data=request.POST, instance=obj, files=request.FILES)
            if form.is_valid():
                new_object = self.save_form(request, form, change=True)
                self.save_model(request, new_object, form, True)
                self.save_related(request, form, formsets, True)
                change_message = self.construct_change_message(request, form, formsets)
                self.log_change(request, new_object, change_message)
                return self.response_change(request, new_object)

        else:
            form = ModelForm(instance=obj)

        # Get Block fieldsets
        fieldsets = self.get_component_fieldsets(request, obj)

        if not self.has_change_permission(request, obj):
            readonly_fields = flatten_fieldsets(fieldsets)
        else:
            readonly_fields = self.get_readonly_fields(request, obj)

        adminForm = helpers.AdminForm(form, fieldsets, {}, readonly_fields, model_admin=self)
        media = self.media + adminForm.media
        formsets = []

        if self.has_change_permission(request, obj):
            title = _('Change %s')
        else:
            title = _('View %s')

        context = {
            **self.admin_site.each_context(request),
            'title': title % opts.verbose_name,
            'subtitle': str(obj) if obj else None,
            'adminform': adminForm,
            'object_id': object_id,
            'original': obj,
            'is_popup': IS_POPUP_VAR in request.POST or IS_POPUP_VAR in request.GET,
            'media': media,
            'inline_admin_formsets': [],
            'errors': helpers.AdminErrorList(form, formsets),
            'app_label': opts.app_label,
            'preserved_filters': self.get_preserved_filters(request),
        }
        context.update(extra_context or {})
        return self.render_change_form(request, context, change=True, obj=obj, form_url=form_url)
