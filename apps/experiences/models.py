from django.contrib.auth import get_user_model
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from apps.core.models import CreatedUpdatedAbstractMixin
from apps.locations.models import Location

User = get_user_model()


class Activity(models.Model):
    name = models.CharField(_("Name"), max_length=255, blank=True)

    class Meta:
        verbose_name = _("Activity")
        verbose_name_plural = _("Activities")

    class Meta:
        verbose_name = _("Activity")
        verbose_name_plural = _("Activities")

    @classmethod
    def get_model_serializer(cls, page):
        from apps.experiences.serializers import ActivitySerializer

        return ActivitySerializer

    def __str__(self):
        return self.name


class Experience(models.Model):
    title = models.CharField(_("Title"), max_length=255)
    slug = models.SlugField(_('Url / Handle'), unique=True)
    description = models.TextField(_("Description"))
    overview = models.TextField(_("Overview"), blank=True)
    image = models.ImageField(_("Image"), upload_to="experiences", blank=True, null=True)
    activity = models.ForeignKey(Activity, related_name='experiences', on_delete=models.SET_NULL, null=True, blank=True)
    location = models.ForeignKey(Location, related_name='experiences', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = _("Experience")
        verbose_name_plural = _("Experiences")

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    @classmethod
    def get_model_serializer(cls, page):
        from apps.experiences.serializers import ExperienceSerializer

        return ExperienceSerializer

    def __str__(self):
        return self.title


class Inclusion(models.Model):
    experience = models.ForeignKey(Experience, related_name='inclusions', on_delete=models.CASCADE)
    description = models.CharField(_("Description"), max_length=255)
    order = models.PositiveSmallIntegerField(_("Order"), default=0)

    class Meta:
        verbose_name = _("Inclusion")
        verbose_name_plural = _("Inclusions")

    def __str__(self):
        return self.description


class WishlistExperience(CreatedUpdatedAbstractMixin):
    user = models.ForeignKey(User, related_name='experience_wishlists', on_delete=models.CASCADE)
    experiences = models.ManyToManyField(Experience, related_name='wishlisted_by', blank=True)

    class Meta:
        verbose_name = _("Wishlist")
        verbose_name_plural = _("Wishlists")

    def __str__(self):
        return f"Wishlist Experience of {self.user}"
