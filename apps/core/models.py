import os
import unicodedata
import uuid
from importlib import import_module
from typing import Any

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex, HashIndex
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import JSONField  # type: ignore
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.encoding import force_str
from django.utils.safestring import mark_safe
from django.utils.timezone import now
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _
from hashid_field import BigHashidAutoField, HashidAutoField
from PIL import ImageFile

from apps.core.managers import UndeletedManager

# Modify image file buffer size.
ImageFile.MAXBLOCK = getattr(settings, 'IMAGE_FILE_MAXBLOCK', 256 * 2**10)

IMAGE_UPLOAD_DIR = getattr(settings, 'IMAGE_UPLOAD_DIR', 'images')

# Look for user function to define file paths
IMAGE_PATH = getattr(settings, 'IMAGE_PATH', None)
if IMAGE_PATH is not None:
    if callable(IMAGE_PATH):
        get_storage_path = IMAGE_PATH
    else:
        parts = IMAGE_PATH.split('.')
        module_name = '.'.join(parts[:-1])
        module = import_module(module_name)
        get_storage_path = getattr(module, parts[-1])
else:

    def get_storage_path(instance, filename):
        model_folder_name = instance._meta.model_name
        try:
            fn = f"{uuid.uuid4()}.{filename.split('.')[-1]}"
        except:
            fn = unicodedata.normalize('NFKD', force_str(filename)).encode('ascii', 'ignore').decode('ascii')
        return os.path.join(IMAGE_UPLOAD_DIR, model_folder_name, fn)


# Default Thumbnail Url Function, this can be overwriten in settings using IMAGE_THUMBNAIL_URL_FUNC
def default_thumbnail_url_func(base_image, **kwargs):
    """
    The default thumbnail url is based on imaginary service
    read the documentation for more use cases.
    - https://github.com/h2non/imaginary
    """
    default_width = kwargs.get('width', getattr(settings, "THUMBNAIL_WIDTH", 100))
    default_height = kwargs.get('height', getattr(settings, "THUMBNAIL_HEIGHT", 75))
    imaginary_url = getattr(settings, 'IMAGINARY_URL', "http://localhost:8088")
    return f"{imaginary_url}/thumbnail?file={base_image.image}&width={default_width}&height={default_height}"


IMAGE_THUMBNAIL_URL_FUNC = getattr(settings, 'IMAGE_THUMBNAIL_URL_FUNC', default_thumbnail_url_func)


class AbstractBaseImage(models.Model):
    image = models.ImageField(_('image'), max_length=255, upload_to=get_storage_path, null=True)
    image_reference = models.CharField(_('image reference'), max_length=255, null=True)

    def image_thumbnail_url_func(self, **kwargs):
        if IMAGE_THUMBNAIL_URL_FUNC is not None and callable(IMAGE_THUMBNAIL_URL_FUNC):
            return IMAGE_THUMBNAIL_URL_FUNC(self, **kwargs)
        return None

    @property
    def admin_thumbnail_url(self):
        default_width = getattr(settings, "ADMIN_THUMBNAIL_WIDTH", 100)
        default_height = getattr(settings, "ADMIN_THUMBNAIL_HEIGHT", 75)
        image_thumbnail_url = self.image_thumbnail_url_func(width=default_width, height=default_height)
        return image_thumbnail_url

    def admin_thumbnail(self):
        default_width = getattr(settings, "ADMIN_THUMBNAIL_WIDTH", 100)
        default_height = getattr(settings, "ADMIN_THUMBNAIL_HEIGHT", 75)
        admin_thumbnail_url = self.image_thumbnail_url_func(width=default_width, height=default_height)
        if admin_thumbnail_url is None:
            return _('An "admin_thumbnail" photo size has not been defined.')
        else:
            return mark_safe(
                f'<img src="{admin_thumbnail_url}" loading="lazy" alt="..." width="{default_width}" height="{default_height}"></a>'
            )

    admin_thumbnail.short_description = _('Thumbnail')

    def to_json(self):
        return {'id': str(self.pk), 'original': self.image.url, 'thumbnail': self.admin_thumbnail_url}

    def display_image(self):
        return self.image.url

    def __str__(self):
        return f"{self.pk}"

    class Meta:
        abstract = True


class AbstractCreatedDateMixin(models.Model):
    created_at = models.DateTimeField(_("created"), auto_now_add=True)

    class Meta:
        abstract = True


class AbstractUpdatedDateMixin(models.Model):
    updated_at = models.DateTimeField(_('updated'), auto_now=True, blank=True)

    def save(self, *args, **kwargs):
        # Force date update
        if self.pk:
            kwargs['update_fields'] = kwargs.get('update_fields', []).append('updated_at')
        super().save(*args, **kwargs)

    class Meta:
        abstract = True


class AbstractCreatedUpdatedDateMixin(AbstractCreatedDateMixin, AbstractUpdatedDateMixin):
    class Meta:
        abstract = True


class AbstractDeletableMixin(models.Model):
    deleted_at = models.DateTimeField(_('deleted'), null=True, blank=True, db_index=True)

    # managers
    objects = models.Manager()
    valid_objects = UndeletedManager()

    def is_deleted(self):
        return self.deleted_at is not None

    is_deleted.boolean = True

    def soft_delete(self):
        self._meta.model.objects.filter(id=self.id, deleted_at__isnull=True).update(deleted_at=timezone.now())

    class Meta:
        abstract = True


class AbstractRandomCodeGeneratorMixin(models.Model):
    code = models.CharField(max_length=20, unique=True)
    code_length = 6

    def save(self, *args, **kwargs):
        # Generate new code if not set
        if not self.code:
            code = self.generate_code()
            self.code = code

        super().save(*args, **kwargs)

    def generate_code(self):
        # Generate Unique Code
        code = get_random_string(length=self.code_length)
        while self._meta.model.objects.filter(code__iexact=code).exists():
            code = get_random_string(length=self.code_length)
        return code

    def regenerate_code(self):
        # Generate Unique Code and Save
        self.code = self.generate_code()
        self.save(update_fields=['code'])
        return self

    class Meta:
        abstract = True


class AbstractUniqueHashIDMixin(models.Model):
    id = HashidAutoField(primary_key=True)

    class Meta:
        indexes = [
            HashIndex(fields=["id"], name="%(class)s_hashid_idx"),
        ]
        abstract = True


class AbstractUniqueBigHashIDMixin(models.Model):
    id = BigHashidAutoField(primary_key=True)

    class Meta:
        indexes = [
            HashIndex(fields=["id"], name="%(class)s_bighashid_idx"),
        ]
        abstract = True


class AbstractMetadata(models.Model):
    private_metadata = JSONField(blank=True, null=True, default=dict)
    metadata = JSONField(blank=True, null=True, default=dict)

    class Meta:
        indexes = [
            GinIndex(fields=["private_metadata"], name="%(class)s_p_meta_idx"),
            GinIndex(fields=["metadata"], name="%(class)s_meta_idx"),
        ]
        abstract = True

    def get_value_from_private_metadata(self, key: str, default: Any = None) -> Any:
        return self.private_metadata.get(key, default)

    def store_value_in_private_metadata(self, items: dict):
        if not self.private_metadata:
            self.private_metadata = {}
        self.private_metadata.update(items)

    def clear_private_metadata(self):
        self.private_metadata = {}

    def delete_value_from_private_metadata(self, key: str):
        if key in self.private_metadata:
            del self.private_metadata[key]

    def get_value_from_metadata(self, key: str, default: Any = None) -> Any:
        return self.metadata.get(key, default)

    def store_value_in_metadata(self, items: dict):
        if not self.metadata:
            self.metadata = {}
        self.metadata.update(items)

    def clear_metadata(self):
        self.metadata = {}

    def delete_value_from_metadata(self, key: str):
        if key in self.metadata:
            del self.metadata[key]


class AbstractSeoMixin(models.Model):
    seo_title = models.CharField(
        _('SEO Title'), max_length=70, help_text=_("Leave blank to use the default title."), blank=True, null=True
    )
    seo_description = models.CharField(
        _('SEO Description'),
        max_length=155,
        help_text=_("Leave blank to use the default description."),
        blank=True,
        null=True,
    )
    seo_image = models.ImageField(
        _('SEO Image'), blank=True, null=True, upload_to='seo_images', help_text="Suggested size: (W:1080px, H:1080px)"
    )

    class Meta:
        abstract = True


class AbstractSlugMixin(models.Model):
    url_handle_validator = RegexValidator(r'^[a-z0-9\/]+(?:-[a-z0-9\/]+)*$', _("This value is invalid."))
    slug = models.CharField(
        _('Url / Handle'),
        validators=[url_handle_validator],
        unique=True,
        max_length=250,
        help_text=_("Example: 'some/slug'."),
    )

    @classmethod
    def get_base_url(cls, lang=None):
        from apps.core.utils import build_lang_url, domain_with_proto

        return domain_with_proto(build_lang_url(lang))

    def get_absolute_url(self, current_lang=None):
        current_lang = current_lang if current_lang else get_language()
        return f'{self.get_base_url(lang=current_lang)}{self.slug}'

    get_absolute_url.short_description = _('Url / Handle')

    class Meta:
        abstract = True


class AbstractPublicationMixin(models.Model):
    publication_date = models.DateTimeField(
        _("publication date"), default=now, help_text=_('When this item should be published.'), db_index=True
    )

    class Meta:
        abstract = True


class AbstractVisibility(AbstractPublicationMixin):
    is_active = models.BooleanField(
        _('active'),
        default=False,
        help_text=_(
            "Designates whether this item should be treated as active. Unselect this instead of deleting items."
        ),
    )
    publication_date = models.DateTimeField(
        _("publication date"), default=now, help_text=_('When this item should be published.'), db_index=True
    )

    class Meta:
        abstract = True


class CreatedAbstractMixin(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class UpdatedAbstractMixin(models.Model):
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class CreatedUpdatedAbstractMixin(CreatedAbstractMixin, UpdatedAbstractMixin):
    class Meta:
        abstract = True
