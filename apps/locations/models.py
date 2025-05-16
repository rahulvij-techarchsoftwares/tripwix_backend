from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.utils import clear_cache_for_keys

from .managers import LocationManager, SubLocationManager


class Country(models.Model):
    name = models.CharField(_("name"), max_length=128)
    alpha2 = models.CharField(
        _("ISO alpha-2"),
        max_length=2,
        primary_key=True,
        help_text="""
            ISO 3166-1 Alpha-2 Code.
            Check possible values here:

            https://www.countrycodeplanet.com/
        """,
    )
    numcode = models.PositiveSmallIntegerField(
        _("ISO numeric"),
        null=True,
        help_text="""
            ISO 3166-1 Numeric Code
            Check possible values here:

            https://www.countrycodeplanet.com/
        """,
    )
    alpha3 = models.CharField(
        max_length=3,
        unique=True,
        help_text="""
            ISO 3166-1 Alpha-3 Code
            Check possible values here:

            https://www.countrycodeplanet.com/
        """,
    )
    phone = models.CharField(
        max_length=3,
        help_text="""
            Phone Indicative
            Check possible values here:

            https://www.countrycodeplanet.com/
        """,
    )
    banner = models.ImageField(_("Banner"), upload_to="country_banners/", blank=True, null=True)

    class Meta:
        verbose_name = _("Country")
        verbose_name_plural = _("Countries")
        ordering = ("name",)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        clear_cache_for_keys("locations")
        super().save(*args, **kwargs)


class CountryVatRate(models.Model):
    country = models.ForeignKey(Country, related_name='vat_rates', on_delete=models.CASCADE)
    name = models.CharField(_("VAT Name"), max_length=100, blank=True)
    description = models.TextField(_("VAT Description"), blank=True)
    rate = models.DecimalField(
        _("Rate"),
        max_digits=5,
        decimal_places=2,
        help_text=_("Value Added Tax Rate"),
    )

    class Meta:
        verbose_name = _("Country VAT Rate")
        verbose_name_plural = _("Country VAT Rates")
        ordering = ("country",)

    def __str__(self):
        return f"{self.country} - {self.rate} %"

    def save(self, *args, **kwargs):
        clear_cache_for_keys("locations")
        super().save(*args, **kwargs)


class Region(models.Model):
    name = models.CharField(_("Region name"), max_length=100)
    slug = models.SlugField(_("Url / Handle"), unique=True)

    class Meta:
        verbose_name = _("Region")
        verbose_name_plural = _("Regions")
        ordering = ("name",)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        clear_cache_for_keys("locations")
        super().save(*args, **kwargs)


class District(models.Model):
    name = models.CharField(_("District Name"), max_length=100)
    slug = models.SlugField(_("Url / Handle"), unique=True)

    class Meta:
        verbose_name = _("District")
        verbose_name_plural = _("Districts")
        ordering = ("name",)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        clear_cache_for_keys("locations")
        super().save(*args, **kwargs)


class City(models.Model):
    name = models.CharField(_("City name"), max_length=100)
    slug = models.SlugField(_("Url / Handle"), unique=True)
    country = models.ForeignKey(Country, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        verbose_name = _("City")
        verbose_name_plural = _("Cities")
        ordering = ("name",)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        clear_cache_for_keys("locations")
        super().save(*args, **kwargs)


class Location(models.Model):
    name = models.CharField(_("Local name"), max_length=100)
    slug = models.SlugField(_("Url / Handle"), unique=True)
    cities = models.ManyToManyField(City, related_name='destinations', blank=True)
    city = models.ForeignKey(City, blank=True, null=True, on_delete=models.SET_NULL)
    district = models.ForeignKey(District, null=True, blank=True, on_delete=models.SET_NULL)
    region = models.ForeignKey(Region, null=True, blank=True, on_delete=models.SET_NULL)
    country = models.ForeignKey(Country, null=True, blank=True, on_delete=models.SET_NULL)
    guide_description = models.TextField(_("Guide Description"), blank=True)
    when_to_leave = models.CharField(_("When to Leave"), max_length=100, blank=True)
    how_to_get_there = models.CharField(_("How to Get There"), max_length=255, blank=True)
    good_to_know = models.TextField(_("Good to Know"), blank=True)
    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_("Designates whether the location appear in the back and front office"),
    )
    active_sublocations = models.BooleanField(
        _("active sublocations"),
        default=True,
        help_text=_("Designates whether the sublocations of this location appear in the front office"),
    )
    sort_order = models.SmallIntegerField(_("order"), default=0)
    banner = models.ImageField(_("Banner"), upload_to="location_banners/", blank=True, null=True)

    objects = LocationManager()

    class Meta:
        verbose_name = _("Destination")
        verbose_name_plural = _("Destinations")
        unique_together = ["slug", "city", "district", "region", "country"]
        ordering = ("sort_order",)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        clear_cache_for_keys("locations")
        super().save(*args, **kwargs)


class SubLocation(models.Model):
    location = models.ForeignKey(Location, on_delete=models.CASCADE)
    name = models.CharField(_("Sub-Local name"), max_length=100)
    slug = models.SlugField(_("Url / Handle"), max_length=150)
    image = models.ImageField(upload_to='sublocations/', blank=True, null=True)
    banner = models.ImageField(_("Banner"), upload_to="sublocation_banner/", blank=True, null=True)

    objects = SubLocationManager()

    class Meta:
        ordering = ("name",)
        verbose_name = _("Community")
        verbose_name_plural = _("Community")
        unique_together = ["slug", "location"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        clear_cache_for_keys("locations")
        super().save(*args, **kwargs)
