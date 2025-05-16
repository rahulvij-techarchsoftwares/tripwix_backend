from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from apps.core.fields import TranslationField
from apps.core.models import AbstractCreatedUpdatedDateMixin, AbstractUniqueHashIDMixin
from apps.media.fields import MediaPhotoForeignKey


class Content(AbstractUniqueHashIDMixin, AbstractCreatedUpdatedDateMixin):
    class Types(models.TextChoices):
        CONTENT = 'cnt', _('Content')
        APP = 'app', _('App')
        IMAGE = 'img', _('Image')

    # model fields
    content_type = models.CharField(_('content type'), choices=Types.choices, max_length=3, default=Types.CONTENT)
    image = MediaPhotoForeignKey()
    app_model = models.ForeignKey(ContentType, blank=True, null=True, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=255, null=True)
    content_object = GenericForeignKey('app_model', 'object_id')
    unique_name = models.CharField(max_length=255, unique=True)
    title = models.CharField(max_length=255)
    content_text = models.TextField(null=True, blank=True)

    i18n = TranslationField(
        fields=(
            'title',
            'content_text',
        )
    )

    class Menu:
        icon = "fa-newspaper"
        indexes = [
            models.Index(fields=["app_model", "object_id"]),
            GinIndex(fields=["i18n"]),
        ]

    def __str__(self):
        return f"{self.unique_name} ({self.pk})"

    @cached_property
    def image_url(self):
        return self.display_image()

    def content_type_display(self):
        CONTENT_TYPE_MAP = {Content.Types.CONTENT: 'text', Content.Types.IMAGE: 'image'}
        if self.content_type == Content.Types.APP and self.app_model_id:
            return f"app:{self.app_model.app_label}.{self.app_model.model}"
        return f"content:{CONTENT_TYPE_MAP.get(self.content_type, self.content_type)}"

    @classmethod
    def get_model_serializer(cls, obj):
        from .serializers import ContentSerializer

        return ContentSerializer
