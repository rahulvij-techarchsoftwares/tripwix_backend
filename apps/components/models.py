from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.indexes import GinIndex
from django.core.validators import RegexValidator
from django.db import models
from django.utils.timezone import now
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _

from apps.core.fields import TranslationField

from .choices import FIELD_APP, FIELD_CHOICES


class ComponentField(models.Model):
    name = models.CharField(_('Name'), max_length=100)
    field_type = models.CharField(_('field type'), choices=FIELD_CHOICES, max_length=20)
    unit = models.CharField(_('unit'), max_length=10, default='', blank=True)

    app_model = models.ForeignKey(ContentType, blank=True, null=True, on_delete=models.SET_NULL)
    app_selectable = models.BooleanField(_('Is Selectable'), default=True)

    i18n = TranslationField(fields=('name',))

    def handle_app_model_creation(self, page):
        model = self.app_model.model_class()

        # TODO (rafa): this needs fix
        if 'create_object_for_page' in dir(model):
            obj = model.create_object_for_page(page)
            return obj.pk

        return None

    class Meta:
        verbose_name = _("Component Field")
        verbose_name_plural = _("Component Fields")
        indexes = [
            GinIndex(fields=["i18n"]),
        ]

    class Menu:
        icon = "fa-tasks"

    def __str__(self):
        return f'{self.name}'


class ComponentFieldOption(models.Model):
    name = models.CharField(_('Name'), max_length=100)
    slug = models.SlugField(_('Handle'), unique=True)
    field = models.ForeignKey(ComponentField, related_name="options", on_delete=models.CASCADE)

    i18n = TranslationField(fields=('name',))

    class Meta:
        verbose_name = _("Component Field Option")
        verbose_name_plural = _("Component Field Options")
        indexes = [
            GinIndex(fields=["i18n"]),
        ]

    def __str__(self):
        return f'{self.name}'


class Component(models.Model):
    name = models.CharField(_('Name'), max_length=100)
    slug = models.SlugField(_('Handle'), unique=True)
    description = models.TextField(_('Description'), blank=True, null=True)

    i18n = TranslationField(
        fields=(
            'name',
            'description',
        )
    )

    class Meta:
        verbose_name = _("Component")
        verbose_name_plural = _("Components")
        indexes = [
            GinIndex(fields=["i18n"]),
        ]

    class Menu:
        icon = "fa-table"

    def __str__(self):
        return f'{self.name}'


class ComponentFields(models.Model):
    component = models.ForeignKey(Component, related_name="component_fields", on_delete=models.CASCADE)
    field = models.ForeignKey(ComponentField, related_name="fields", on_delete=models.CASCADE)
    name = models.CharField(_('Name'), max_length=100)
    slug = models.SlugField(_('Handle'))
    item_o = models.IntegerField(_('Sort order'), default=0)
    is_required = models.BooleanField(_('Is required'), default=False)
    is_translatable = models.BooleanField(_('Is translatable'), default=False)
    is_multiple = models.BooleanField(_('Is multiple'), default=False)

    i18n = TranslationField(fields=('name',))

    class Meta:
        unique_together = (
            'component',
            'slug',
        )
        verbose_name = _("component Field")
        verbose_name_plural = _("component Fields")
        indexes = [
            GinIndex(fields=["i18n"]),
        ]
        ordering = ['item_o']

    def __str__(self):
        return f'{self.name}'


class CollectionType(models.Model):
    name = models.CharField(_('Name'), max_length=100)
    slug = models.SlugField(_('Handle'), unique=True)
    is_internal = models.BooleanField(_('is internal'), default=False)

    i18n = TranslationField(fields=('name',))

    class Meta:
        verbose_name = _("Collection Type")
        verbose_name_plural = _("Collection Types")
        indexes = [
            GinIndex(fields=["i18n"]),
        ]

    class Menu:
        icon = "fa-object-ungroup"

    def __str__(self):
        return f'{self.name}'


class CollectionTypeComponents(models.Model):
    component = models.ForeignKey(Component, related_name="collection_types", on_delete=models.CASCADE)
    collection_type = models.ForeignKey(CollectionType, related_name="components", on_delete=models.CASCADE)
    item_o = models.IntegerField(_('Sort order'), default=0)

    class Meta:
        ordering = ['item_o']
        verbose_name = _("Collection component")
        verbose_name_plural = _("Collection components")

    def __str__(self):
        return f'{self.component} - {self.collection_type}'


class AbstractCollection(models.Model):
    collection_type = models.ForeignKey(CollectionType, on_delete=models.CASCADE)
    fields_data_json = models.JSONField(_('Data'), blank=True, null=True)

    class Meta:
        abstract = True
        indexes = [
            GinIndex(fields=["fields_data_json"]),
        ]

    def save(self, *args, **kwargs):
        created = self.pk is None
        super(AbstractCollection, self).save(*args, **kwargs)
        if created:
            fields_to_json = {}
            for collection_type_components in self.collection_type.components.all():
                for component_fields in collection_type_components.component.component_fields.all():
                    field = component_fields.field
                    # concatenate so we can use the same block in the same collection
                    field_slug = f'b{collection_type_components.pk}-{component_fields.slug}'
                    if field.field_type == FIELD_APP and not field.app_selectable:
                        obj_id = field.handle_app_model_creation(self)
                        if obj_id:
                            fields_to_json[field_slug] = obj_id
            self.fields_data_json = fields_to_json
            self.save(update_fields=['fields_data_json'])
