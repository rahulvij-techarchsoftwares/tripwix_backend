from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.components.models import ComponentField
from apps.core.fields import TranslationField
from apps.core.models import AbstractCreatedUpdatedDateMixin, AbstractSlugMixin

from .query import ComponentFormQuerySet


class ComponentForm(AbstractSlugMixin, AbstractCreatedUpdatedDateMixin):
    title = models.CharField(_('Title'), max_length=140)
    is_active = models.BooleanField(
        _('active'),
        default=False,
        help_text=_(
            "Designates whether this item should be treated as active. Unselect this instead of deleting items."
        ),
    )

    objects = models.Manager.from_queryset(ComponentFormQuerySet)()

    class Meta:
        verbose_name = _("Form")
        verbose_name_plural = _("Forms")

    class Menu:
        icon = "fa-align-left"

    def __str__(self):
        return f'{self.title}'

    @classmethod
    def get_model_serializer(cls, obj):
        from .serializers import ComponentFormSerializer

        return ComponentFormSerializer


class ComponentFormFields(models.Model):
    form = models.ForeignKey(ComponentForm, related_name="form_fields", on_delete=models.CASCADE)
    field = models.ForeignKey(ComponentField, related_name="forms", on_delete=models.CASCADE)
    name = models.CharField(_('Name'), max_length=100)
    slug = models.SlugField(_('Handle'))
    item_o = models.IntegerField(_('Sort order'), default=0)
    is_required = models.BooleanField(_('Is required'), default=False)
    is_multiple = models.BooleanField(_('Is multiple'), default=False)

    i18n = TranslationField(fields=('name',))

    class Meta:
        unique_together = (
            'form',
            'slug',
        )
        verbose_name = _("form Field")
        verbose_name_plural = _("form Fields")
        indexes = [
            GinIndex(fields=["i18n"]),
        ]
        ordering = ['item_o']

    def __str__(self):
        return f'{self.name}'
