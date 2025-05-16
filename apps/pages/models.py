from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.forms import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.components.models import AbstractCollection
from apps.core.fields import TranslationField
from apps.core.models import AbstractCreatedUpdatedDateMixin, AbstractSeoMixin, AbstractSlugMixin, AbstractVisibility

from .query import PageQuerySet


def validate_video_file(value):
    valid_extensions = ['.mp4', '.avi', '.mov', '.wmv', '.mkv']
    ext = value.name.split('.')[-1].lower()
    if f".{ext}" not in valid_extensions:
        raise ValidationError(
            _('Unsupported file extension. Allowed extensions are: %(extensions)s'),
            params={'extensions': ', '.join(valid_extensions)},
        )


class AbstractPage(
    AbstractCollection, AbstractSlugMixin, AbstractSeoMixin, AbstractVisibility, AbstractCreatedUpdatedDateMixin
):
    title = models.CharField(_('Title'), max_length=140)

    i18n = TranslationField(
        fields=(
            'title',
            'slug',
            'seo_title',
            'seo_description',
        )
    )

    objects = models.Manager.from_queryset(PageQuerySet)()

    class Meta:
        abstract = True
        indexes = AbstractCollection.Meta.indexes + [
            GinIndex(fields=["i18n"]),
        ]

    def __str__(self):
        return f'{self.title}'


class Page(AbstractPage):
    video = models.FileField(
        _('Video'),
        upload_to='videos',
        null=True,
        blank=True,
        help_text=_('Upload a video file for this page.'),
        validators=[validate_video_file],
    )

    class Meta:
        db_table = 'pages_page'
        verbose_name = _("Page")
        verbose_name_plural = _("Pages")
        indexes = AbstractPage.Meta.indexes

    class Menu:
        icon = "fa-file"
