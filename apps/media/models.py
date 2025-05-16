from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.urls import reverse
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from photologue.models import ImageModel

from apps.core.fields import TranslationField
from apps.core.models import AbstractCreatedUpdatedDateMixin, AbstractUniqueBigHashIDMixin

from .fields import MediaPhotoField

# TODO: Taggable Manager
# from dengun_cms.core.managers import TaggableManager


class MediaPhoto(ImageModel):
    caption = models.CharField('caption', blank=True, null=True, max_length=128)
    # tags = TaggableManager(blank=True)

    class Meta:
        db_table = 'media_photo'
        verbose_name = "photo"
        verbose_name_plural = "photos"
        ordering = [
            '-pk',
        ]

    class Menu:
        icon = "fa-picture-o"

    def admin_photo_thumbnail(self):
        if hasattr(self, "get_admin_media_url"):
            return self.get_admin_media_url()
        return self.image.url

    def to_json(self):
        return {'id': self.pk, 'original': self.image.url, 'thumbnail': self.admin_photo_thumbnail()}

    def __str__(self):
        if self.caption:
            return u"%s" % self.caption
        return u"%s" % self.pk

    @classmethod
    def get_model_serializer(cls, obj):
        from apps.media.serializers import MediaPhotoSerializer

        return MediaPhotoSerializer


class MediaGallery(models.Model):
    title = models.CharField('title', max_length=50, unique=True)
    description = models.TextField('description', blank=True)
    photos = MediaPhotoField(verbose_name='photos', related_name='media_gallery', blank=True)

    slug = models.SlugField('Url / Handle', unique=True)
    # CATEGORIZE
    # tags = TaggableManager(blank=True)
    # VISIBILITY
    date_added = models.DateTimeField(auto_now_add=True, blank=True)
    publication_date = models.DateTimeField(
        "publication date", default=now, help_text='When the gallery should go live.', db_index=True
    )
    is_active = models.BooleanField(
        'active',
        default=True,
        help_text="Designates whether this gallery should be treated as active. Unselect this instead of deleting articles.",
    )
    is_featured = models.BooleanField(
        'featured', default=False, help_text="Designates whether this gallery should be treated as featured."
    )
    is_public = models.BooleanField(
        'is public', default=True, help_text='Public galleries will be displayed in the default views.'
    )
    enable_comments = models.BooleanField('enable comments', default=False)

    class Meta:
        db_table = 'media_gallery'
        verbose_name = 'Gallery'
        verbose_name_plural = 'Galleries'

    class Menu:
        icon = "fa-camera"

    def __str__(self):
        return u"%s" % self.title

    def cover(self):
        return self.photos.first()

    @classmethod
    def get_base_url(cls):
        try:
            from django.contrib.sites.models import Site

            domain = "http://%s" % Site.objects.get_current().domain
        except:
            domain = "http://example.com"

        try:
            reverse_url = reverse('media_gallery', args=("",))
        except:
            reverse_url = "/"

        return domain + reverse_url


class MediaDocument(AbstractUniqueBigHashIDMixin, AbstractCreatedUpdatedDateMixin):
    title = models.CharField(_('Title'), max_length=60, blank=False)
    description = models.CharField(_('Description'), max_length=250, blank=True, null=True)
    file_object = models.FileField(_('File'), upload_to='documents', blank=False)

    i18n = TranslationField(
        fields=(
            'title',
            'description',
        )
    )

    class Meta:
        verbose_name = _('Document')
        verbose_name_plural = _("Documents")
        indexes = [
            GinIndex(fields=["i18n"]),
        ]

    class Menu:
        icon = 'fa-file-word'

    def __str__(self):
        return f"{self.title}"

    @classmethod
    def get_model_serializer(cls, obj):
        from .serializers import SimpleMediaDocumentSerializer

        return SimpleMediaDocumentSerializer
