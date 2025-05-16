import logging
import random
import re
import uuid
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from multiprocessing import Value

from django.conf import settings
from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.gis.db import models
from django.core.cache import cache
from django.core.validators import MaxValueValidator, MinValueValidator, validate_comma_separated_integer_list
from django.db import transaction
from django.db.models import Count, F, IntegerField, Max, Min, OuterRef, Q, Subquery
from django.db.models.functions import Abs
from django.templatetags.static import static
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from jsonschema import ValidationError
from photologue.models import IMAGE_FIELD_MAX_LENGTH, ImageModel

from apps.core.models import AbstractCreatedUpdatedDateMixin
from apps.core.services import RedisContextManager
from apps.locations.models import City, Country, Location, SubLocation
from apps.media.fields import MediaPhotoField
from apps.properties.choices import SyncStatusChoices
from apps.properties.utils import ExchangeRateService
from tripwix_backend.celery import app

from .choices import (
    ACCOUNT_TYPE_CHOICES,
    CONTACT_METHOD_CHOICES,
    DETAIL_TYPE_BOOL,
    DETAIL_TYPE_CHOICES,
    DETAIL_TYPE_COLOR,
    DETAIL_TYPE_DATE,
    DETAIL_TYPE_DESCRIPTION,
    DETAIL_TYPE_INTEGER,
    DETAIL_TYPE_INTEGER_OPTIONS,
    DETAIL_TYPE_INTEGER_SUM,
    DETAIL_TYPE_NUMBER,
    DETAIL_TYPE_OPTION,
    DETAIL_TYPE_OPTIONS,
    DETAIL_TYPE_RATING,
    DETAIL_TYPE_TEXT,
    DETAIL_TYPE_TIME,
    DETAIL_TYPE_TRANS_DESCRIPTION,
    DETAIL_TYPE_TRANS_TEXT,
    FEE_TYPE_CHOICES,
    ONBOARDING_SOURCE_CHOICES,
    OPTION_CAN_ADD_RELATED,
    OPTION_CAN_CHANGE_RELATED,
    OPTION_CAN_DELETE_RELATED,
    PREFERRED_LANGUAGE_CHOICES,
    PROPERTIES_SORT_ORDER_CHOICES,
    RATE_TYPE_CHOICES,
    SALE_TYPE_CHOICES,
    SEASON_CHOICES,
)
from .managers import PropertyQuerysetManager, PropertyTypeManager


class PropertyGroup(models.Model):
    name = models.CharField(_("name"), max_length=100)
    sale_type = models.CharField(
        _("Sale type"),
        max_length=1,
        choices=SALE_TYPE_CHOICES,
        default="d",
        unique=True,
    )
    description = models.TextField(_("description"), default="", blank=True)

    # SEO STUFF
    seo_title = models.CharField(
        _("SEO Title"),
        max_length=70,
        help_text=_("Leave blank to use the default title."),
        blank=True,
    )
    seo_description = models.CharField(
        _("SEO Description"),
        max_length=155,
        help_text=_("Leave blank to use the default description."),
        blank=True,
    )
    seo_keywords = models.CharField(
        _("SEO Keywords"),
        max_length=255,
        help_text=_("Leave blank to use the default keywords."),
        blank=True,
    )
    slug = models.SlugField(_("Url / Handle"), unique=True)

    # RELATION
    details = models.ManyToManyField("Detail", related_name="group", through="PropertyGroupDetails")

    # FRONTEND SETTINGS
    price_ranges = models.CharField(
        _("Price Ranges"),
        max_length=160,
        default="",
        blank=True,
        validators=[validate_comma_separated_integer_list],
        help_text=_("To enable price filtering specify the ranges. eg. 100,200,300."),
    )
    in_search = models.BooleanField(_("Search-able"), help_text=_("Allow this group to be searched"), default=False)

    sort_order_fe = models.CharField(
        _("Sort order Front-end"),
        max_length=2,
        choices=PROPERTIES_SORT_ORDER_CHOICES,
        default="ne",
        help_text=_("Initial ordering of properties in the Front-end"),
    )
    sort_order_be = models.CharField(
        _("Sort order Back-end"),
        max_length=2,
        choices=PROPERTIES_SORT_ORDER_CHOICES,
        default="ne",
        help_text=_("Initial ordering of properties in the Back-end"),
    )

    def details_queryset(self):
        return PropertyGroupDetails.objects.filter(property_group=self)

    # def get_base_url(self):
    #     return self.get_absolute_url()

    # TODO: property group urls
    # def get_absolute_url(self):
    #     if self.slug:
    #         return reverse('properties:group', kwargs={'slug': self.slug})
    #     return reverse('properties:group', kwargs={'id': self.pk})

    class Meta:
        db_table = "property_sale_group"
        verbose_name = _("Property Group")
        verbose_name_plural = _("Property Groups")

    def __str__(self):
        return self.name


class DetailCategory(models.Model):
    name = models.CharField(_("Name"), max_length=100)
    slug = models.SlugField(_("Url / Handle"), unique=True)
    icon = models.CharField(_("Icon"), max_length=100, blank=True)
    item_o = models.IntegerField(_("Order"), default=0)

    class Meta:
        verbose_name = _("Detail Category")
        verbose_name_plural = _("Detail Categories")
        ordering = ("item_o",)

    def __str__(self):
        return self.name


class Currency(models.Model):
    CODE_CHOICES = [
        ('USD', 'US Dollar'),
        ('EUR', 'Euro'),
        ('GBP', 'British Pound'),
        ('MXN', 'Mexican Peso'),
    ]

    POSITION_CHOICES = [
        ('before', 'Before'),
        ('after', 'After'),
    ]

    code = models.CharField(max_length=3, choices=CODE_CHOICES, primary_key=True, unique=True)
    symbol = models.CharField(max_length=5)
    position = models.CharField(max_length=10, choices=POSITION_CHOICES, default='before')
    rate = models.DecimalField(
        max_digits=20, decimal_places=10, default=Decimal('1.0'), help_text="Exchange rate relative to EUR."
    )
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Currency"
        verbose_name_plural = "Currencies"
        db_table = "currency"

    def __str__(self):
        return f"{self.code}: {self.rate}"

    def clean(self):
        super().clean()
        if not self.symbol:
            raise ValidationError('The "symbol" field cannot be empty.')
        if not self.position:
            raise ValidationError('The "position" field cannot be empty.')

    @classmethod
    def save_in_cache(cls, code, rate):
        with RedisContextManager() as cache:
            cache_key = f"currency_{code}"
            cache.setex(
                name=cache_key,
                time=settings.CURRENCY_UPDATE_INTERVAL,
                value=str(rate),
            )

    @classmethod
    def get_from_cache(cls, code='EUR'):
        try:
            with RedisContextManager() as cache:
                cache_key = f"currency_{code}"
                return cache.get(cache_key)
        except Exception as e:
            logging.error(f"Error getting currency from cache: {str(e)}")
            return None

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.save_in_cache(self.code, self.rate)


class DetailCategorySection(models.Model):
    category = models.ForeignKey(DetailCategory, related_name="sections", on_delete=models.CASCADE)
    name = models.CharField(_("Name"), max_length=100)
    description = models.TextField(_("Description"), blank=True)
    slug = models.SlugField(_("Url / Handle"))
    item_o = models.IntegerField(_("Order"), default=0)

    class Meta:
        verbose_name = _("Detail Category Section")
        verbose_name_plural = _("Detail Category Sections")
        ordering = (
            "category",
            "item_o",
        )
        unique_together = (("category", "name"),)

    def __str__(self):
        return f"{self.category} > {self.name}"


class Detail(models.Model):
    name = models.CharField(_("name"), max_length=100)
    slug = models.SlugField(_("Internal Handle"), unique=True)
    detail_type = models.CharField(_("detail type"), choices=DETAIL_TYPE_CHOICES, max_length=31)
    sort_order = models.SmallIntegerField(_("order"), default=0)
    unit = models.CharField(_("unit"), max_length=10, blank=True, help_text=_("units used by type field"))
    help_text = models.CharField(_("help text"), max_length=250, blank=True)

    # For pre-populated Fields
    initial_text_value = models.CharField(_("default text"), max_length=128, blank=True)
    initial_bool_value = models.BooleanField(_("default boolean"), default=False, blank=True)
    initial_description_value = models.TextField(_("default description"), blank=True)
    initial_number_value = models.DecimalField(
        _("default number decimal"),
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )
    initial_integer_value = models.IntegerField(_("default number"), default=0, blank=True, null=True)
    initial_date_value = models.DateField(_("default date"), null=True, blank=True)
    initial_time_value = models.TimeField(_("default time"), null=True, blank=True)
    initial_number_with_value_type_selector_value = models.CharField(
        _("default number with value type selector"),
        max_length=1,
        choices=FEE_TYPE_CHOICES,
        default="p",
    )

    # DETAIL_TYPE_OPTION, DETAIL_TYPE_OPTIONS
    admin_related_opts_permissions = models.CharField(
        _("Admin related options permissions"),
        max_length=8,
        blank=True,
        validators=[validate_comma_separated_integer_list],
    )
    in_search = models.BooleanField(_("Searchable"), help_text=_("Allow this detail to be searched"), default=False)

    class Meta:
        verbose_name = _("Detail")
        verbose_name_plural = _("Details")
        ordering = [
            "sort_order",
        ]

    def __str__(self):
        return f"[{self.name}] {self.get_detail_type_display()}"

    def _admin_related_opts_permissions(self):
        opts = self.admin_related_opts_permissions
        items = list()
        if opts:
            items = opts.split(",")
        return items

    @property
    def can_add_related(self):
        if OPTION_CAN_ADD_RELATED in self._admin_related_opts_permissions():
            return True
        return False

    @property
    def can_change_related(self):
        if OPTION_CAN_CHANGE_RELATED in self._admin_related_opts_permissions():
            return True
        return False

    @property
    def can_delete_related(self):
        if OPTION_CAN_DELETE_RELATED in self._admin_related_opts_permissions():
            return True
        return False

    def _form_id(self):
        return "%s_%s" % (DETAIL_TYPE_OPTIONS, self.pk)

    form_id = property(_form_id)

    @property
    def verbose_name(self):
        return self.name


class PropertyGroupDetails(models.Model):
    property_group = models.ForeignKey(PropertyGroup, on_delete=models.CASCADE, blank=False)
    detail = models.ForeignKey(Detail, on_delete=models.CASCADE)
    section = models.ForeignKey(DetailCategorySection, on_delete=models.CASCADE)
    is_required = models.BooleanField(_("is required"), default=True)
    is_filter = models.BooleanField(_("is filter"), default=False)
    sort_order = models.SmallIntegerField(_("order"), default=0)

    class Meta:
        verbose_name = _("Detail")
        verbose_name_plural = _("Details")
        ordering = ["section", "sort_order"]
        unique_together = ["property_group", "detail"]

    def __str__(self):
        return f"[{self.property_group}] {self.detail.name}"


class PropertyType(models.Model):
    name = models.CharField(_("Name"), max_length=100)
    slug = models.SlugField(_("Url / Handle"), unique=True)
    item_o = models.IntegerField(_("Order"), default=0)

    objects = PropertyTypeManager()

    class Meta:
        verbose_name = _("Property Type")
        verbose_name_plural = _("Property Types")
        ordering = ("item_o",)

    def __str__(self):
        return self.name


class PropertyTypology(models.Model):
    name = models.CharField(_("Name"), max_length=50)
    slug = models.SlugField(_("Url / Handle"), unique=True)
    item_o = models.IntegerField(_("Order"), default=0)

    class Meta:
        verbose_name = _("Typology")
        verbose_name_plural = _("Typologies")
        ordering = (
            "name",
            "item_o",
        )

    def __str__(self):
        return self.name


class AccountIDAutoIncrementMixin(models.Model):
    def save(self, *args, **kwargs):
        if not self.pk:
            with transaction.atomic():
                max_account_id = self.__class__.objects.aggregate(max_account_id=models.Max('account_id'))[
                    'max_account_id'
                ]
                self.account_id = max_account_id + 1 if max_account_id else 1
        super().save(*args, **kwargs)

    class Meta:
        abstract = True


class PropertyManager(AccountIDAutoIncrementMixin):
    name = models.CharField(_("Name"), max_length=100)
    account_id = models.IntegerField(unique=True)
    last_name = models.CharField(_("First Name"), max_length=100, blank=True, null=True)
    first_name = models.CharField(_("Last Name"), max_length=100, blank=True, null=True)
    language = models.CharField(
        _("Preferred Language"), choices=PREFERRED_LANGUAGE_CHOICES, blank=True, max_length=5, null=True
    )
    email = models.EmailField(_("Property Manager Email 1"), null=True, blank=True)
    phone = models.CharField(_("Phone 1"), blank=True, max_length=500, null=True)
    notes = models.TextField(_("Notes 1"), blank=True, null=True)
    contact_method = models.CharField(
        _("Preferred Contact Method"),
        choices=CONTACT_METHOD_CHOICES,
        blank=True,
        null=True,
    )

    email_2 = models.EmailField(_("Property Manager Email 2"), null=True, blank=True)
    phone_2 = models.CharField(_("Phone 2"), blank=True, max_length=500, null=True)
    notes_2 = models.TextField(_("Contact Notes 2"), blank=True, null=True)
    street = models.CharField(_("Street Name and Number"), max_length=500, blank=True, null=True)
    city = models.ForeignKey(City, null=True, blank=True, on_delete=models.SET_NULL)
    state = models.CharField(_("State and Province"), max_length=500, blank=True, null=True)
    zip_code = models.CharField(_("Zip Code"), max_length=100, blank=True, null=True)
    country = models.ForeignKey(Country, null=True, blank=True, on_delete=models.SET_NULL)
    percentage = models.DecimalField(_("Percentage"), max_digits=5, decimal_places=2, blank=True, null=True)
    concierge_phone = models.CharField(_("Concierge Phone"), blank=True, max_length=500, null=True)
    concierge_email = models.EmailField(_("Concierge Email"), blank=True, null=True)
    comments = models.TextField(_("Comments"), blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)

    def __str__(self):
        return "%s" % self.name


class PropertyOwnership(AccountIDAutoIncrementMixin):
    name = models.CharField(_("Name"), max_length=100)
    slug = models.SlugField(_("Url / Handle"), unique=True)
    account_id = models.IntegerField(unique=True)
    last_name = models.CharField(_("First Name"), max_length=100, blank=True, null=True)
    first_name = models.CharField(_("Last Name"), max_length=100, blank=True, null=True)
    language = models.CharField(
        _("Preferred Language"), choices=PREFERRED_LANGUAGE_CHOICES, blank=True, max_length=5, null=True
    )
    email = models.EmailField(_("Reservation Email 1"), null=True, blank=True)
    phone = models.CharField(_("Reservation Phone 1"), blank=True, max_length=500, null=True)
    notes = models.TextField(_("Notes 1"), blank=True, null=True)
    contact_method = models.CharField(
        _("Preferred Contact Method"),
        choices=CONTACT_METHOD_CHOICES,
        blank=True,
        null=True,
    )
    email_2 = models.EmailField(_("Reservation Email 2"), null=True, blank=True)
    phone_2 = models.CharField(_("Reservation Phone 2"), blank=True, max_length=500, null=True)
    notes_2 = models.TextField(_("Contact Notes 2"), blank=True, null=True)
    street = models.CharField(_("Street Name and Number"), max_length=500, blank=True, null=True)
    city = models.ForeignKey(City, null=True, blank=True, on_delete=models.SET_NULL)
    state = models.CharField(_("State and Province"), max_length=500, blank=True, null=True)
    zip_code = models.CharField(_("Zip Code"), max_length=100, blank=True, null=True)
    country = models.ForeignKey(Country, null=True, blank=True, on_delete=models.SET_NULL)
    account_type = models.CharField(_("Account Type"), choices=ACCOUNT_TYPE_CHOICES, blank=True, null=True)
    company_legal_name = models.CharField(_("Company Name"), max_length=500, blank=True, null=True)
    tax_id = models.CharField(_("Tax ID"), max_length=100, blank=True, null=True)
    onboarding_contact = models.CharField(_("Onboarding Contact"), max_length=500, blank=True, null=True)
    onboarding_source = models.CharField(
        _("Onboarding Source"), choices=ONBOARDING_SOURCE_CHOICES, max_length=13, blank=True, null=True
    )
    comments = models.TextField(_("Comments"), blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = _("Ownership")
        verbose_name_plural = _("Ownerships")
        ordering = ("name",)

    def __str__(self):
        return self.name


class PropertyMediaPhoto(ImageModel):
    image = models.ImageField(_("image"), max_length=IMAGE_FIELD_MAX_LENGTH)
    caption = models.CharField(_("caption"), blank=True, null=True, max_length=128)
    # TODO: Tags
    # tags = TaggableManager(blank=True)
    alt_text = models.CharField(_("Alternative text"), blank=True, null=True, max_length=128)
    order = models.IntegerField(_("order"), default=0)
    is_synched = models.BooleanField(default=False)

    class Meta:
        db_table = "property_media_photo"
        verbose_name = _("photo")
        verbose_name_plural = _("photos")
        ordering = ("order",)

    class Menu:
        icon = "fa-picture-o"

    def admin_photo_thumbnail(self):
        if hasattr(self, "get_admin_media_url"):
            return self.get_admin_media_url()
        return self.image.url

    def to_json(self):
        return {
            "id": self.pk,
            "original": self.image.url,
            "thumbnail": self.admin_photo_thumbnail(),
        }

    def __str__(self):
        if self.caption:
            return "%s" % self.caption
        return "%s" % self.pk


class PropertyCategory(models.Model):
    name = models.CharField(_("Name"), max_length=100)
    slug = models.SlugField(_("Url / Handle"), unique=True)
    is_active = models.BooleanField(_("Active"), default=True)

    class Meta:
        verbose_name = _("Property Category")
        verbose_name_plural = _("Property Categories")
        ordering = ("name",)

    def __str__(self):
        return self.name


class Rate(models.Model):
    property = models.ForeignKey('Property', related_name='rates', on_delete=models.CASCADE)
    from_date = models.DateField(_("From (date)"))
    to_date = models.DateField(_("To (date)"))
    season = models.CharField(_("Season"), max_length=10, choices=SEASON_CHOICES, blank=True)
    minimum_nights = models.PositiveIntegerField(_("Minimum Nights"))
    website_sales_value = models.DecimalField(
        _("Website & Sales value"), max_digits=10, decimal_places=2, help_text=_("Value in Euros (€)")
    )

    class Meta:
        unique_together = ('property', 'from_date', 'to_date')

    def __str__(self):
        return f"{self.property.name} - {self.season} ({self.from_date} to {self.to_date})"

    def get_previous_rate(self):
        if self.from_date and self.property:
            return Rate.objects.filter(property=self.property, to_date__lt=self.from_date).order_by('-to_date').first()
        return None

    def save(self, *args, **kwargs):
        from apps.properties.tasks import task_update_listing_price

        super().save(*args, **kwargs)
        if not self.property.hostify_id:
            return
        formatted_from_date = timezone.datetime.strftime(self.from_date, '%Y-%m-%d')
        formatted_to_date = timezone.datetime.strftime(self.to_date, '%Y-%m-%d')

        task_update_listing_price.delay(
            str(self.website_sales_value), formatted_from_date, formatted_to_date, int(self.property.hostify_id)
        )


class Ambassador(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    photo = models.ImageField(upload_to='ambassadors/', null=True, blank=True)

    def __str__(self):
        return self.name


class Property(models.Model):
    uid = models.UUIDField(default=uuid.uuid4, editable=False)
    ambassador = models.ForeignKey(
        Ambassador, on_delete=models.SET_NULL, null=True, blank=True, related_name='properties'
    )
    name = models.CharField(_("Name"), max_length=180, null=True, blank=True)
    title = models.CharField(_("Title"), max_length=180, null=True, blank=True, help_text=_("Public Name"))
    content = models.TextField(_("Description"), null=True, blank=True)
    reference = models.CharField(_("Reference"), max_length=50, unique=True)

    # TODO: Media
    # MEDIA
    photos = MediaPhotoField(to=PropertyMediaPhoto, can_select=False, blank=True)

    # SEO STUFF
    seo_title = models.CharField(
        _("SEO Title"),
        max_length=500,
        help_text=_("Leave blank to use the default property title."),
        blank=True,
    )
    seo_description = models.CharField(
        _("SEO Description"),
        max_length=500,
        help_text=_("Leave blank to use the default property description."),
        blank=True,
    )
    tagline = models.CharField(
        _("Tagline"),
        max_length=255,
        help_text=_("Tagline for the property"),
        blank=True,
    )
    slug = models.SlugField(
        _("Slug"),
        unique=True,
        blank=True,
        max_length=255,
    )

    # TODO: Tags
    # CATEGORIZE
    # tags = TaggableManager(
    # through=PropertyTaggedItem, max_items=6, blank=True)

    # VISIBILITY
    publication_date = models.DateTimeField(
        _("publication date"),
        default=timezone.now,
        null=True,
        blank=True,
        db_index=True,
        help_text=_("When the property should go live."),
    )
    publication_end_date = models.DateTimeField(
        _("publication end date"),
        null=True,
        blank=True,
        db_index=True,
        help_text=_("When to expire the property. Leave empty to never expire."),
    )
    is_active = models.BooleanField(
        _("active"),
        default=False,
        help_text=_(
            "Designates whether this property should be treated as active. Unselect this instead of deleting properties."
        ),
    )
    hostify_id = models.CharField(max_length=255, unique=True, null=True, blank=True)

    # VISIBILITY - FEATURED
    featured_date = models.DateTimeField(
        _("featured publication date"),
        null=True,
        blank=True,
        default=timezone.now,
        db_index=True,
        help_text=_("When the property should go live."),
    )
    featured_end_date = models.DateTimeField(
        _("featured publication end date"),
        null=True,
        blank=True,
        help_text=_("When to expire the featured property. Leave empty to never expire."),
        db_index=True,
    )
    is_featured = models.BooleanField(
        _("featured"),
        default=False,
        blank=True,
        help_text=_("Designates whether this property should be treated as featured."),
    )

    # BASE
    property_group = models.ForeignKey(PropertyGroup, null=True, blank=True, on_delete=models.SET_NULL)
    property_type = models.ForeignKey(PropertyType, blank=True, null=True, on_delete=models.SET_NULL)
    property_category = models.ForeignKey(PropertyCategory, blank=True, null=True, on_delete=models.SET_NULL)
    typology = models.ForeignKey(PropertyTypology, blank=True, null=True, on_delete=models.SET_NULL)

    location = models.ForeignKey(
        Location,
        verbose_name=_("destination"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    sublocation = models.ForeignKey(
        SubLocation,
        verbose_name=_("community"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    address = models.CharField(_("Address"), max_length=250, blank=True, null=True)
    point = models.PointField(_("Coordinates"), serialize=False, blank=True, null=True, spatial_index=False)
    tax_id = models.CharField(_("Permit/Tax ID"), max_length=100, blank=True, null=True)

    # DETAILS
    details = models.ManyToManyField(PropertyGroupDetails, through="PropertyDetailValues", blank=True, null=True)
    # INTERNAL STACK
    _details = list()
    # RELATED PROPERTIES
    related = models.ManyToManyField("self", blank=True)

    # ENTITIES
    commission = models.DecimalField(
        _("Commission"),
        max_digits=13,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Not visible for public"),
    )
    commission_type = models.CharField(
        _("Commission Rate"),
        max_length=5,
        null=True,
        blank=True,
        choices=RATE_TYPE_CHOICES,
        default="p",
    )
    ownership = models.ForeignKey(
        PropertyOwnership,
        verbose_name=_("Ownership"),
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    manager = models.ForeignKey(
        PropertyManager,
        verbose_name=_("Manager"),
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    know_before_you_go = models.TextField(_("Know Before You Go"), blank=True, null=True)
    rental_price_included = models.TextField(_("Rental Price Included"), blank=True, null=True)

    # OTHER
    date_added = models.DateTimeField(auto_now_add=True, blank=True)
    date_updated = models.DateTimeField(_("updated"), auto_now=True, blank=True)
    created_by = models.ForeignKey(
        User,
        verbose_name=_("Created by"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    note = models.TextField(_("Note"), blank=True, help_text=_("Not visible for public"))
    item_o = models.IntegerField(_("Order"), default=0, blank=True)
    standard_photos_url = models.CharField(blank=True)
    standard_photos_synced = models.BooleanField(default=False)

    objects = PropertyQuerysetManager()

    amenities = models.ManyToManyField(
        "Amenity",
        blank=True,
        help_text="Click to select active amenities.<br/>Light blue means they will be seen in the Website.<br/>Delete by selecting one then pressing Backspace.<br/>",
    )
    default_price = models.DecimalField(_("Default Price"), max_digits=10, decimal_places=2, null=True, blank=True)
    default_price_eur = models.DecimalField(
        _("Default Price in EUR (€)"), max_digits=10, decimal_places=2, null=True, blank=True
    )
    ready_to_sync = models.BooleanField(_("Ready to Sync"), default=False)
    last_synced_at = models.DateTimeField(_("Last Synced At"), null=True, blank=True)
    last_synced_payload = models.JSONField(_("Last Synced Payload"), null=True, blank=True)
    changes_to_sync = models.JSONField(_("Changes to Sync"), null=True, blank=True)
    needs_calendar_creation = models.BooleanField(_("Needs Calendar Creation"), default=False)
    sync_status = models.CharField(
        _("Sync Status"), max_length=12, choices=SyncStatusChoices.choices, default=SyncStatusChoices.NOT_SYNCED
    )

    def get_absolute_url(self):
        sale_type = self.property_group.sale_type
        if sale_type == "s" and hasattr(self, "saleproperty"):
            return self.saleproperty.get_absolute_url()
        if sale_type == "r" and hasattr(self, "rentalproperty"):
            return self.rentalproperty.get_absolute_url()
        return ""

    def get_class_name(self):
        return str(self.__class__.__name__).lower()

    @property
    def is_poa(self):
        sale_type = self.property_group.sale_type
        if sale_type == "s" and hasattr(self, "saleproperty"):
            return self.saleproperty.poa
        return False

    def get_rental_price(self):
        try:
            now = timezone.now()
            rates_queryset = self.rates.filter(Q(Q(from_date__gte=now) | Q(to_date__gte=now)))
            if rates_queryset:
                min_value = rates_queryset.aggregate(Min('website_sales_value'))['website_sales_value__min']
                max_value = rates_queryset.aggregate(Max('website_sales_value'))['website_sales_value__max']
                return {'min': min_value, 'max': max_value}
        except Exception as e:
            logging.error(e)
        return None

    def price(self):
        sale_type = self.property_group.sale_type if self.property_group else None

        if sale_type == "s" and hasattr(self, "saleproperty"):
            base_price_eur = self.saleproperty.get_price()
            if base_price_eur:
                if not self.default_price_eur or self.default_price_eur != base_price_eur:
                    self.default_price_eur = base_price_eur
                    self.save(update_fields=['default_price_eur'])

                converted = self.get_prices_in_currencies()
                converted['EUR'] = f"${self.default_price_eur}"
                return converted
            else:
                return {}

        elif sale_type == "r":
            rental_range = self.get_rental_price()
            if rental_range and rental_range.get('min') and rental_range.get('max'):
                price_data = self.get_prices_in_currencies(rental_range)
                return price_data
            else:
                return {}

        else:
            return {}

    def get_prices_in_currencies(self, price_range=None):
        exchange_service = ExchangeRateService
        currency_model = Currency
        prices = {}

        if price_range and 'min' in price_range and 'max' in price_range:
            min_val = Decimal(price_range['min'])
            max_val = Decimal(price_range['max'])
            for code in exchange_service.DESIRED_CURRENCIES:
                symbol = exchange_service.SYMBOLS.get(code, '?')
                rate = currency_model.get_from_cache(code)
                if not rate:
                    rate_obj = currency_model.objects.filter(code=code).first()
                    if rate_obj:
                        rate = rate_obj.rate
                        currency_model.save_in_cache(code, rate)
                    else:
                        rate = '1.0'

                rate = Decimal(rate)
                try:
                    if code == 'EUR':
                        min_converted = min_val
                        max_converted = max_val
                    else:
                        min_converted = min_val * rate
                        max_converted = max_val * rate
                    min_converted = min_converted.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
                    max_converted = max_converted.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
                    prices[code] = f"{symbol}{min_converted} - {symbol}{max_converted}"
                except Exception as e:
                    logging.error(f"Error converting interval for {code}: {str(e)}")
                    prices[code] = None
            return prices

        base_val = self.default_price_eur or self.default_price
        if not base_val:
            return {}

        base_val = Decimal(base_val)
        for code in exchange_service.DESIRED_CURRENCIES:
            symbol = exchange_service.SYMBOLS.get(code, '?')
            rate = currency_model.get_from_cache(code)
            if not rate:
                rate_obj = currency_model.objects.filter(code=code).first()
                if rate_obj:
                    rate = rate_obj.rate
                    currency_model.save_in_cache(code, rate)
                else:
                    rate = '1.0'

            rate = Decimal(rate)
            try:
                converted_val = base_val if code == 'USD' else (base_val * rate)
                converted_val = converted_val.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
                prices[code] = f"{symbol}{converted_val}"
            except Exception as e:
                logging.error(f"Error converting for {code}: {str(e)}")
                prices[code] = None

        return prices

    @property
    def latitude(self):
        return self.point.x if self.point else None

    @property
    def longitude(self):
        return self.point.y if self.point else None

    @property
    def thumbnail_url(self):
        thumbnail_url = self.get_thumbnail_url()
        if thumbnail_url:
            return thumbnail_url
        return static("admin/images/no_thumb.png")

    def get_thumbnail(self):
        try:
            thumbnail_url = self.get_thumbnail_url()
        except AttributeError:
            thumbnail_url = None
        if thumbnail_url:
            return '<img src="%s">' % thumbnail_url
        thumb_static = static("admin/images/no_thumb.png")
        return f'<img src="{thumb_static}" width="60">'

    get_thumbnail.allow_tags = True
    get_thumbnail.short_description = _("thumbnail")

    def get_thumbnail_url(self):
        cache_key = f"property_thumbnail_url_{self.pk}"
        cached_thumbnail = cache.get(cache_key)

        if cached_thumbnail is not None:
            return cached_thumbnail

        try:
            slides = self.photos.first()
            thumbnail_url = slides.get_admin_thumbnail_url()
            if thumbnail_url:
                cache.set(cache_key, thumbnail_url, 1800)
                return thumbnail_url
        except:
            pass

        cache.set(cache_key, None, 1800)
        return None

    def get_drive_folder(self):
        drive_base_url = "https://drive.google.com/drive/folders/"
        folder = self.standard_photos_url.replace(drive_base_url, "")
        folder_id = folder.split("?")[0]
        return folder_id

    def reorganize_divisions(self):
        division_types = self.divisions.values_list('division_type', flat=True).distinct()
        for division_type in division_types:
            divisions = self.divisions.filter(division_type=division_type).order_by('id')
            for i, division in enumerate(divisions):
                division.name = f"{division.division_type} {i + 1}"
                division.save()

    def get_number_of_bedrooms(self):
        return self.divisions.filter(division_type__name='Bedroom').count()

    def get_number_of_bathrooms(self):
        return self.divisions.filter(division_type__name='Bathroom').count()

    def get_num_guests(self):
        return (
            self.detail_values.filter(property_group_detail__detail__slug='maxGuests')
            .values_list('integer_value', flat=True)
            .first()
        )

    def get_similar_properties(self, limit=7):
        try:
            num_bedrooms = self.num_bedrooms
            num_guests = self.num_guests or 0
            num_bathrooms = self.num_bathrooms

            min_bedrooms = max(num_bedrooms - 3, 0)
            max_bedrooms = num_bedrooms + 3
            min_guests = max(num_guests - 6, 0)
            max_guests = num_guests + 6
            min_bathrooms = max(num_bathrooms - 3, 0)
            max_bathrooms = num_bathrooms + 6

            similar_properties = (
                Property.objects.filter(location=self.location, is_active=True)
                .exclude(id=self.id)
                .annotate(
                    num_bedrooms=Count('divisions', filter=Q(divisions__division_type__slug='bedroom')),
                    num_bathrooms=Count('divisions', filter=Q(divisions__division_type__slug='bathroom')),
                    num_guests=Subquery(
                        PropertyDetailValues.objects.filter(
                            property_object=OuterRef('pk'), property_group_detail__detail__slug='maxGuests'
                        ).values('integer_value')[:1],
                        output_field=IntegerField(),
                    ),
                    guest_distance=Abs(F('num_guests') - num_guests),
                )
                .filter(
                    num_bedrooms__gte=min_bedrooms,
                    num_bedrooms__lte=max_bedrooms,
                    num_bathrooms__gte=min_bathrooms,
                    num_bathrooms__lte=max_bathrooms,
                    num_guests__gte=min_guests,
                    num_guests__lte=max_guests,
                )
                .prefetch_related('photos', 'location')
                .order_by('guest_distance')[:limit]
            )
            return similar_properties
        except Exception as e:
            logging.error(f"Error getting similar properties: {str(e)}")
            return None

    def update_property_slugs(self):
        parts = []
        if self.location and self.location.name:
            parts.append(slugify(self.location.name))
        detail_tagline = self.tagline
        if detail_tagline:
            parts.append(slugify(detail_tagline))
        parts.append(str(self.reference))
        return '/'.join(parts)

    class Meta:
        verbose_name = _("Property")
        verbose_name_plural = _("Properties")
        ordering = ("-item_o",)
        permissions = (
            ("can_sync_property", "Can Sync Property"),
            ("can_publish_property", "Can Publish Property"),
            ("can_change_vat_rate", "Can Change Property VAT Rate"),
        )
        indexes = [
            models.Index(fields=['item_o'], name='property_item_o_idx'),
        ]

    def __str__(self):
        return self.name

    @classmethod
    def get_model_serializer(cls, obj):
        from apps.properties.api.serializers import PropertySerializer

        return PropertySerializer

    def save(self, *args, **kwargs):
        self.slug = self.update_property_slugs()
        if self.pk:
            try:
                old_instance = Property.objects.get(pk=self.pk)
                if not self.tagline and old_instance.tagline:
                    self.tagline = old_instance.tagline
                if not self.ambassador and old_instance.ambassador:
                    self.ambassador = old_instance.ambassador
            except Property.DoesNotExist:
                pass
        super().save(*args, **kwargs)

        from apps.properties.tasks import task_construct_next_payload

        selected_delay = random.randint(1, 20)
        task_construct_next_payload.apply_async((str(self.id),), countdown=selected_delay)

    def sync_changes_with_hostify(self):
        from apps.properties.tasks import task_sync_with_hostify

        selected_delay = random.randint(1, 20)
        task_sync_with_hostify.apply_async((str(self.id),), countdown=selected_delay)


class PropertyAmenity(models.Model):
    property = models.ForeignKey(Property, related_name='property_amenities', on_delete=models.CASCADE)
    amenity = models.ForeignKey("Amenity", related_name='properties', on_delete=models.CASCADE)


class PropertyDivisionType(models.Model):
    name = models.CharField(_("Name"), max_length=100)
    slug = models.SlugField(_("Url / Handle"), unique=True)
    item_o = models.IntegerField(_("Order"), default=0)

    class Meta:
        verbose_name = _("Division Type")
        verbose_name_plural = _("Division Types")
        ordering = ("item_o",)

    def __str__(self):
        return self.name


class PropertyDivisionExtra(models.Model):
    name = models.CharField(_("Name"), max_length=100)

    class Meta:
        verbose_name = _("Division Extra")
        verbose_name_plural = _("Division Extras")

    def __str__(self):
        return self.name


class PropertyDivision(models.Model):
    property_object = models.ForeignKey(Property, related_name="divisions", on_delete=models.CASCADE)
    division_type = models.ForeignKey(PropertyDivisionType, on_delete=models.CASCADE)
    name = models.CharField(_("Name"), max_length=100)
    description = models.CharField(_("description"), blank=True, null=True, max_length=250)
    extra = models.ManyToManyField(PropertyDivisionExtra, blank=True, null=True)

    class Meta:
        verbose_name = _("Division")
        verbose_name_plural = _("Divisions")

    def __str__(self):
        return self.name


class PropertyBedroomsConfigBedType(models.Model):
    name = models.CharField(_("Name"), max_length=100)
    slug = models.SlugField(_("Url / Handle"), unique=True)
    item_o = models.IntegerField(_("Order"), default=0)

    class Meta:
        verbose_name = _("Bed Type")
        verbose_name_plural = _("Bed Types")
        ordering = ("item_o",)

    def __str__(self):
        return self.name


class PropertyBedroomsConfig(models.Model):
    property_object = models.ForeignKey(Property, related_name="bedrooms_configurations", on_delete=models.CASCADE)
    division = models.ForeignKey(
        PropertyDivision,
        verbose_name=_("division"),
        on_delete=models.CASCADE,
    )
    bed_type = models.ForeignKey(
        PropertyBedroomsConfigBedType,
        verbose_name=_("type bed"),
        on_delete=models.CASCADE,
    )
    number = models.IntegerField(
        _("number beds"),
        blank=True,
        null=True,
        default=1,
        choices=[
            (None, ""),
        ]
        + [(i, i) for i in range(0, 11)],
    )

    class Meta:
        verbose_name = _("Bedroom Configuration")
        verbose_name_plural = _("Bedrooms Configuration")


class PropertyRatingScore(models.Model):
    property_object = models.ForeignKey(Property, related_name="ratings", on_delete=models.CASCADE)
    score = models.DecimalField(
        _("score"), max_digits=2, decimal_places=1, validators=[MinValueValidator(0.0), MaxValueValidator(5.0)]
    )
    name = models.CharField(_("name"), max_length=120, blank=True)
    testimonial = models.TextField(_("testimonial"), blank=True)
    date = models.DateField(_("date"), default=timezone.now)
    city = models.CharField(_("city"), max_length=30, blank=True)
    country = models.CharField(_("country"), max_length=30, blank=True)
    state = models.CharField(_("state"), max_length=30, blank=True)

    def __str__(self):
        return f"{self.property_object} - {self.score}"


class DetailOption(models.Model):
    detail = models.ForeignKey(Detail, related_name="options", on_delete=models.CASCADE)
    name = models.CharField(_("name"), max_length=200, blank=True)
    slug = models.SlugField(_("slug"), max_length=200, blank=True)
    sort_order = models.SmallIntegerField(_("order"), default=0, blank=True)

    class Meta:
        verbose_name = _("Option")
        verbose_name_plural = _("Options")
        ordering = [
            "sort_order",
        ]
        unique_together = (("detail", "slug"),)

    def __str__(self):
        return self.name


class PropertyDetailValues(models.Model):
    property_object = models.ForeignKey(Property, related_name="detail_values", on_delete=models.CASCADE)
    property_group_detail = models.ForeignKey(PropertyGroupDetails, on_delete=models.CASCADE)
    detail_option = models.ForeignKey(
        DetailOption,
        related_name="option_value",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    detail_options = models.ManyToManyField(DetailOption, related_name="options_value", blank=True)

    # details
    text_value = models.CharField(_("text"), max_length=255, blank=True)
    bool_value = models.BooleanField(_("boolean"), default=False, blank=True)
    description_value = models.TextField(_("description"), blank=True)
    number_value = models.DecimalField(_("number decimal"), max_digits=8, decimal_places=2, null=True, blank=True)
    integer_value = models.IntegerField(_("number"), default=0, blank=True, null=True)
    date_value = models.DateField(_("date"), null=True, blank=True)
    time_value = models.TimeField(_("time"), null=True, blank=True)
    # TODO: Image
    # image_value = models.ImageField(_('image'),
    #                                 upload_to=settings.PHOTOLOGUE_PATH,
    #                                 null=True, blank=True)

    _options = list()

    class Meta:
        ordering = [
            "property_group_detail",
        ]
        db_table = "property_detail_values"
        verbose_name = _("Property Detail Value")
        verbose_name_plural = _("Property Detail Values")
        unique_together = (
            "property_object",
            "property_group_detail",
        )

    def __hash__(self):
        return super().__hash__()

    @property
    def detail(self):
        return None

    def get_value(self, detail_type):
        value = None
        if detail_type == DETAIL_TYPE_TEXT:
            return self.text_value

        elif detail_type == DETAIL_TYPE_BOOL:
            return self.bool_value

        elif detail_type == DETAIL_TYPE_DATE:
            return self.date_value

        elif detail_type == DETAIL_TYPE_TIME:
            return self.time_value

        elif detail_type == DETAIL_TYPE_NUMBER:
            return self.number_value

        elif detail_type == DETAIL_TYPE_INTEGER:
            return self.integer_value

        elif detail_type == DETAIL_TYPE_COLOR:
            return self.text_value

        elif detail_type == DETAIL_TYPE_DESCRIPTION:
            return self.description_value

        elif detail_type == DETAIL_TYPE_OPTION:
            return self.detail_option

        elif detail_type in (DETAIL_TYPE_OPTIONS, DETAIL_TYPE_INTEGER_OPTIONS):
            return self.options

        elif detail_type in (DETAIL_TYPE_TRANS_DESCRIPTION, DETAIL_TYPE_TRANS_TEXT):
            return self.description_value

        elif detail_type == DETAIL_TYPE_RATING:
            return self.number_value

        elif detail_type == DETAIL_TYPE_INTEGER_SUM:
            if not self.text_value:
                # For defaults
                return self.integer_value
            return self.text_value

        return self.text_value

    def __set_value(self, _type, value):
        if value is None:
            return None
        else:
            return _type(value)

    def set_value(self, detail_type, value):
        from html import unescape

        if detail_type == DETAIL_TYPE_TEXT:
            if value is not None:
                try:
                    value = unescape(value)
                except Exception as e:
                    logging.error(e)
            self.text_value = self.__set_value(str, value)

        elif detail_type == DETAIL_TYPE_BOOL:
            self.bool_value = self.__set_value(bool, value)

        elif detail_type == DETAIL_TYPE_DATE:
            self.date_value = value

        elif detail_type == DETAIL_TYPE_TIME:
            self.time_value = value

        elif detail_type == DETAIL_TYPE_NUMBER:
            self.number_value = self.__set_value(Decimal, value)

        elif detail_type == DETAIL_TYPE_INTEGER:
            self.integer_value = self.__set_value(int, value)

        elif detail_type == DETAIL_TYPE_COLOR:
            self.text_value = value

        elif detail_type == DETAIL_TYPE_OPTION:
            self.detail_option = value

        elif detail_type in (DETAIL_TYPE_OPTIONS, DETAIL_TYPE_INTEGER_OPTIONS):
            self.detail_options.set(value)
        elif detail_type == DETAIL_TYPE_DESCRIPTION:
            self.description_value = value

        elif detail_type in (DETAIL_TYPE_TRANS_DESCRIPTION, DETAIL_TYPE_TRANS_TEXT):
            # SKIP THIS (handled externally)
            pass

        elif detail_type == DETAIL_TYPE_RATING:
            self.number_value = self.__set_value(Decimal, value)

        elif detail_type == DETAIL_TYPE_INTEGER_SUM:
            # text value
            self.text_value = value

            # integer value
            numbers = re.findall("([0-9]+)", value)
            total = sum(map(int, numbers))
            self.integer_value = int(total)
        else:
            self.text_value = value

        return self.value

    @property
    def is_translable(self):
        detail_type = self.property_group_detail.detail.detail_type
        if detail_type and detail_type in (
            DETAIL_TYPE_TRANS_DESCRIPTION,
            DETAIL_TYPE_TRANS_TEXT,
        ):
            return True
        return False

    def _get_value_by_language(self, detail_type, language=None):
        if detail_type in (DETAIL_TYPE_TRANS_DESCRIPTION, DETAIL_TYPE_TRANS_TEXT):
            return getattr(self, "description_value_%s" % language, self.value)

        elif detail_type in (DETAIL_TYPE_OPTIONS, DETAIL_TYPE_INTEGER_OPTIONS):
            option_name = getattr(self.value, "name_%s" % language, self.value.name)
            if option_name:
                return "%s" % option_name
        return "%s" % self.value

    def __eq__(self, other):
        return (
            isinstance(other, self.__class__)
            and self.property_group_detail == other.property_group_detail
            and self.value == other.value
        )

    @property
    def detail(self):
        return self.property_group_detail.detail

    def add_value(self, value):
        self.set_value(self.property_group_detail.detail.detail_type, value)
        self.save()
        return value

    @property
    def value(self):
        return self.get_value(self.property_group_detail.detail.detail_type)

    @property
    def options(self):
        if self._options:
            return self._options
        if self.pk:
            return list(self.detail_options.all())
        return list()

    @options.setter
    def options(self, value):
        if value:
            self._options = value
        else:
            self._options = None

    def get_value_by_language(self, language=None):
        detail_type = self.property_group_detail.detail.detail_type
        return self._get_value_by_language(detail_type, language=language)

    def __str__(self):
        if self.property_group_detail.detail.detail_type in (
            DETAIL_TYPE_OPTIONS,
            DETAIL_TYPE_INTEGER_OPTIONS,
        ):
            return "multiple options"
        return f"{self.value}"


class Amenity(models.Model):
    name = models.CharField(_("Name"), max_length=100)
    slug = models.SlugField(_("Url / Handle"), unique=True)
    item_o = models.IntegerField(_("Order"), default=0)
    category = models.ForeignKey("AmenityCategory", related_name="amenities", on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name = _("Amenity")
        verbose_name_plural = _("Amenities")
        ordering = ("item_o",)

    def __str__(self):
        return self.name


class AmenityCategory(models.Model):
    name = models.CharField(_("Name"), max_length=100)
    slug = models.SlugField(_("Url / Handle"), unique=True)
    item_o = models.IntegerField(_("Order"), default=0)

    class Meta:
        verbose_name = _("Amenity Category")
        verbose_name_plural = _("Amenity Categories")
        ordering = ("item_o",)

    def __str__(self):
        return self.name


class Wishlist(models.Model):
    user = models.ForeignKey(User, related_name='wishlists', on_delete=models.CASCADE)
    property = models.ForeignKey(Property, related_name='wishlisted_by', on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Wishlist")
        verbose_name_plural = _("Wishlists")
        unique_together = ('user', 'property')

    def __str__(self):
        return f"{self.user}'s wishlist item: {self.property}"


class PropertyTax(AbstractCreatedUpdatedDateMixin):
    property = models.ForeignKey(Property, related_name='taxes', on_delete=models.CASCADE)
    tax_object = models.JSONField(_("Tax Object"), null=True, blank=True)

    class Meta:
        verbose_name = _("Property Tax")
        verbose_name_plural = _("Property Taxes")

    def __str__(self):
        return f"{self.property}"

    def is_stale(self):
        return not self.tax_object or self.updated_at < timezone.now() - timezone.timedelta(hours=1)
