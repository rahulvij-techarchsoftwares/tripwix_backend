import json
import logging

from django.db import models
from django.db.models import Avg, CharField, Count, IntegerField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import serializers

from apps.hostify.utils import get_fees_from_cache, process_fee_data
from apps.locations.serializers import BaseLocationSerializer, SubLocationSerializer
from apps.media.serializers import MediaPhotoSerializer
from apps.pages.models import Page
from apps.properties.models import Amenity, Property, PropertyDetailValues, PropertyTax, Wishlist
from apps.properties.utils import ExchangeRateService, get_property_availability


class GoogleAPINotificationSerializer(serializers.Serializer):
    pass


class AmbassadorSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    photo = serializers.ImageField()
    description = serializers.CharField()


class PointSerializer(serializers.Serializer):
    lat = serializers.FloatField(source='y')
    lng = serializers.FloatField(source='x')


class HostifyWebhookSerializer(serializers.Serializer):
    id = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    status = serializers.CharField(allow_blank=True, allow_null=True)
    checkIn = serializers.CharField(allow_blank=True, allow_null=True)
    checkOut = serializers.CharField(allow_blank=True, allow_null=True)
    notes = serializers.CharField(allow_blank=True, allow_null=True)
    listing_id = serializers.CharField(allow_blank=True, allow_null=True)


class SimilarPropertySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    slug = serializers.SlugField()
    property_url = serializers.SlugField(source='slug')
    title = serializers.CharField()
    location = serializers.CharField(source='location.name', read_only=True, allow_null=True)
    num_bedrooms = serializers.IntegerField(source='get_number_of_bedrooms', read_only=True)
    num_bathrooms = serializers.IntegerField(source='get_number_of_bathrooms', read_only=True)
    num_guests = serializers.IntegerField(source='get_num_guests', read_only=True)
    price = serializers.JSONField()
    thumbnail_url = serializers.SerializerMethodField()
    rating_avg = serializers.DecimalField(max_digits=3, decimal_places=1, read_only=True)
    photo = serializers.SerializerMethodField()
    tagline = serializers.CharField(read_only=True)

    def get_thumbnail_url(self, obj):
        thumbnail_url = obj.get_thumbnail_url()
        return thumbnail_url

    def get_photo(self, obj):
        first_photo = obj.photos.first()
        if first_photo and hasattr(first_photo, 'image'):
            return first_photo.image.url
        return None


class PropertySerializer(serializers.ModelSerializer):
    property_url = serializers.SlugField(source='slug')
    location_name = serializers.CharField(source='location.name', read_only=True)
    sublocation_name = serializers.CharField(source='sublocation.name', read_only=True)
    amenities = serializers.SlugRelatedField(many=True, slug_field='name', queryset=Amenity.objects.all())
    rating_avg = serializers.SerializerMethodField()
    rating_count = serializers.SerializerMethodField()

    class Meta:
        model = Property
        fields = (
            'id',
            'slug',
            'property_url',
            'title',
            'tagline',
            'location_name',
            'sublocation_name',
            'amenities',
            'price',
            'thumbnail_url',
            'rating_avg',
            'rating_count',
        )

    def get_rating_avg(self, obj):
        ratings = obj.ratings.all()
        if ratings.exists():
            avg_rating = ratings.aggregate(models.Avg('score'))['score__avg']
            if avg_rating is not None:
                return round(avg_rating, 1)
        return None

    def get_rating_count(self, obj):
        return obj.ratings.count()


class RatingSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    score = serializers.DecimalField(max_digits=2, decimal_places=1)
    name = serializers.CharField()
    testimonial = serializers.CharField()
    date = serializers.DateField()
    city = serializers.CharField()
    country = serializers.CharField()
    state = serializers.CharField()


class CommunitySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    banner = serializers.ImageField()


class BasePropertySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    slug = serializers.SlugField()
    title = serializers.CharField()
    tagline = serializers.CharField()
    location_slug = serializers.CharField(source='location_slug_annotated', read_only=True)
    property_category_name = serializers.SerializerMethodField()
    default_price_eur = serializers.CharField()
    location = serializers.CharField(source='location.name', read_only=True, allow_null=True)
    sublocation = serializers.CharField(source='sublocation.name', read_only=True, allow_null=True)
    price = serializers.JSONField()
    property_url = serializers.SlugField(source='slug')
    photos = MediaPhotoSerializer(many=True)
    num_guests = serializers.IntegerField()
    curator = serializers.CharField(read_only=True)
    bedbath = serializers.CharField()
    num_bedrooms = serializers.IntegerField()
    num_bathrooms = serializers.IntegerField()
    design_type = serializers.CharField()
    coordinates = PointSerializer(source='point')
    rating_average = serializers.FloatField(source='rating_avg', read_only=True)
    rating_count = serializers.IntegerField(read_only=True)
    special_offer_line = serializers.CharField(read_only=True)
    sublocation_image = serializers.ImageField(source='sublocation.image', read_only=True)
    community = CommunitySerializer(source='sublocation', read_only=True)
    country_alpha2 = serializers.CharField(source='location.country.alpha2', read_only=True)
    seo_title = serializers.CharField()
    seo_description = serializers.CharField()
    available_from = serializers.DateField(required=False)
    available_to = serializers.DateField(required=False)
    cancellation_policy = serializers.CharField(required=False)
    check_in_time = serializers.TimeField(required=False)
    check_out_time = serializers.TimeField(required=False)
    has_wifi = serializers.BooleanField(default=False)
    has_parking = serializers.BooleanField(default=False)
    is_pet_friendly = serializers.BooleanField(default=False)
    property_type = serializers.CharField(required=False)
    license_number = serializers.CharField(required=False)
    host_name = serializers.CharField(source='host.name', read_only=True)

    def get_property_category_name(self, obj):
        category = getattr(obj, 'property_category', None)
        return category.name if category else None


class RoomSerializer(serializers.Serializer):
    division = serializers.CharField(source='division.name')
    bed_type = serializers.CharField(source='bed_type.name')
    num_beds = serializers.IntegerField(source='number')


class AmenitySerializer(serializers.Serializer):
    name = serializers.CharField()
    slug = serializers.SlugField()
    item_o = serializers.IntegerField()


class PropertyDetailSerializer(BasePropertySerializer):
    hostify_id = serializers.CharField()
    description = serializers.CharField(source='content')
    tax_id = serializers.CharField()
    yt_video_url = serializers.CharField()
    tripwix_video_url = serializers.CharField()
    owner_video_url = serializers.CharField()
    amenities = serializers.SerializerMethodField()
    rooms = RoomSerializer(many=True, source='bedrooms_configurations')
    similar_properties = serializers.SerializerMethodField()
    minimum_nights = serializers.IntegerField()
    ambassador = AmbassadorSerializer(read_only=True)
    know_before_you_go = serializers.CharField(source='know_before_you_go_detail')
    Living_Areas = serializers.CharField()
    Location_para = serializers.CharField()
    location_Description = serializers.CharField()
    location_extra = serializers.CharField()
    Special_Features = serializers.CharField()
    rental_price_included = serializers.CharField(source='rental_price_included_detail')
    rating = RatingSerializer(source='ratings', many=True)
    instant_booking = serializers.BooleanField()
    special_offer_description = serializers.CharField()
    sublocation = SubLocationSerializer(allow_null=True, read_only=True)
    full_description = serializers.CharField(required=False)
    # reviews = ReviewSerializer(many=True, read_only=True)
    latitude = serializers.FloatField(source='point.latitude', read_only=True)
    longitude = serializers.FloatField(source='point.longitude', read_only=True)
    discounts = serializers.JSONField(required=False)
    nearby_attractions = serializers.ListField(child=serializers.CharField(), required=False)
    living_area_sq_meters = serializers.FloatField(required=False)
    special_features = serializers.ListField(child=serializers.CharField(), required=False)
    floor_number = serializers.IntegerField(required=False)
    heating_type = serializers.CharField(required=False)
    air_conditioning = serializers.BooleanField(default=False)
    elevator = serializers.BooleanField(default=False)

    def get_similar_properties(self, obj):
        similar_properties = obj.get_similar_properties(limit=7)
        return SimilarPropertySerializer(similar_properties, many=True).data

    @staticmethod
    def get_amenities(obj):
        amenities = obj.amenities.all()
        return AmenitySerializer(amenities, many=True).data


class FeeAndAvailabilitySerializer(serializers.Serializer):
    availability = serializers.SerializerMethodField()
    calculated_fees = serializers.SerializerMethodField()

    def get_availability(self, obj):
        if not obj.hostify_id:
            return None

        instant_booking = obj.detail_values.filter(property_group_detail__detail__slug='instantBooking').first()
        if not instant_booking or not instant_booking.value:
            return None

        start_date = self.context.get('start_date')
        end_date = self.context.get('end_date')

        total_availability = get_property_availability(obj, start_date, end_date)
        return total_availability

    def get_calculated_fees(self, obj):
        if not obj.hostify_id:
            return None

        instant_booking = obj.detail_values.filter(property_group_detail__detail__slug='instantBooking').first()
        if not instant_booking or not instant_booking.value:
            return None

        start_date = self.context.get('start_date')
        end_date = self.context.get('end_date')
        total_period = (end_date - start_date).days

        rates = (
            obj.rates.filter(Q(from_date__lte=end_date) & Q(to_date__gte=start_date)).distinct().order_by('from_date')
        )

        total_price = 0
        covered_dates = set()
        property_price = 0

        transformed_fees = get_fees_from_cache(obj.hostify_id)
        if not transformed_fees:
            db_tax = PropertyTax.objects.filter(property=obj).first()
            if not (db_tax and db_tax.tax_object):
                return None
            try:
                if isinstance(db_tax.tax_object, str):
                    transformed_fees = json.loads(db_tax.tax_object)
                    if isinstance(transformed_fees, dict):
                        transformed_fees = [transformed_fees]
                elif isinstance(db_tax.tax_object, dict):
                    transformed_fees = [db_tax.tax_object]
                elif isinstance(db_tax.tax_object, list):
                    transformed_fees = db_tax.tax_object
            except json.JSONDecodeError as e:
                logging.error(f'Error decoding Fee payload for property {obj.id} - {e}')
                return None

        for rate in rates:
            range_start = max(rate.from_date, start_date)
            range_end = min(rate.to_date, end_date)
            current = range_start
            while current <= range_end:
                covered_dates.add(current)
                current += timezone.timedelta(days=1)

            period_days = len([d for d in covered_dates if range_start <= d <= range_end])
            property_price += rate.website_sales_value * period_days

        remaining_days = total_period - len(covered_dates)
        if remaining_days > 0 and obj.default_price:
            property_price += obj.default_price or 0 * period_days

        processed_fees = process_fee_data(transformed_fees, property_price)
        total_price += processed_fees.get('property_price', 0)
        total_price += processed_fees.get('remaining_sum_by_night', 0) * remaining_days

        final_price_eur = float(f'{total_price:.2f}')

        rates = ExchangeRateService.get_rates()
        symbols = ExchangeRateService.SYMBOLS

        calculated_fees_multi_currency = {
            currency: f"{symbols.get(currency, '')}{round(final_price_eur * float(rate), 2)}"
            for currency, rate in rates.items()
        }

        return calculated_fees_multi_currency


class NameSlugSerializer(serializers.Serializer):
    name = serializers.CharField()
    slug = serializers.SlugField()


class NameSlugTypeSerializer(NameSlugSerializer):
    type = serializers.CharField()


class PropertyCategorySerializer(NameSlugSerializer):
    pass


class AmenitySerializer(NameSlugSerializer):
    pass


class DestinationSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    banner = serializers.ImageField()
    communities = CommunitySerializer(many=True)


class CountrySerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    banner = serializers.ImageField()
    destinations = DestinationSerializer(many=True)


class PriceRangeSerializer(serializers.Serializer):
    website_sales_value__min = serializers.IntegerField()
    website_sales_value__max = serializers.IntegerField()


class PropertyFilterSerializer(serializers.Serializer):
    countries = CountrySerializer(many=True)
    num_guests = serializers.ListField(child=serializers.IntegerField())
    categories = PropertyCategorySerializer(many=True)
    price_range = PriceRangeSerializer()
    num_bedrooms = serializers.ListField(child=serializers.IntegerField())
    num_bathrooms = serializers.ListField(child=serializers.IntegerField())
    amenities = AmenitySerializer(many=True)
    dates = serializers.ListField(child=serializers.DateField(), allow_empty=True)
    sort_by = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    currencies = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    instant_booking = serializers.ListField(child=serializers.BooleanField(), allow_empty=True)
    special_offers = serializers.ListField(child=serializers.BooleanField(), allow_empty=True)
    booking_type = NameSlugSerializer(many=True)
    lifestyle = NameSlugSerializer(many=True)
    acessibilities = NameSlugTypeSerializer(many=True)
    design_types = NameSlugSerializer(many=True)

    def to_representation(self, instance):
        data_types = {
            'countries': 'multi_select',
            'dates': 'date_range',
            'num_guests': 'multi_select',
            'categories': 'multi_select',
            'price_range': 'range',
            'num_bedrooms': 'multi_select',
            'num_bathrooms': 'multi_select',
            'amenities': 'multi_select',
            'sort_by': 'select',
            'currencies': 'select',
            'instant_booking': 'multi_select',
            'special_offers': 'multi_select',
            'booking_type': 'multi_select',
            'lifestyle': 'multi_select',
            'acessibilities': None,
            'design_types': 'multi_select',
        }
        data = super().to_representation(instance)
        transformed_dict = {}
        for key, value in data.items():
            transformed_dict[key] = {
                'type': data_types.get(key),
                'value': value,
            }
        return transformed_dict


class WishlistSerializer(serializers.ModelSerializer):
    property = serializers.SerializerMethodField()
    property_id = serializers.PrimaryKeyRelatedField(
        queryset=Property.objects.all(), write_only=True, source='property'
    )

    class Meta:
        model = Wishlist
        fields = ['id', 'property', 'property_id', 'created']
        read_only_fields = ['id', 'created', 'property']

    def get_property(self, obj):
        prop_id = obj.property_id
        if not prop_id:
            return None

        now = timezone.now()
        today = now.date()

        room_counts = (
            Property.objects.filter(pk=OuterRef('pk'))
            .annotate(
                bedroom_count=Count('divisions', filter=Q(divisions__division_type__slug='bedroom')),
                bathroom_count=Count('divisions', filter=Q(divisions__division_type__slug='bathroom')),
            )
            .values('bedroom_count', 'bathroom_count')[:1]
        )

        detail_values = PropertyDetailValues.objects.filter(property_object=OuterRef('pk'))

        property_qs = (
            Property.objects.filter(pk=prop_id)
            .prefetch_related(
                'ratings',
                'photos',
                'property_amenities__amenity',
                'property_group',
                'location__country',
                'sublocation',
            )
            .annotate(
                rating_avg=Coalesce(Avg('ratings__score', distinct=True), Value(None)),
                rating_count=Count('ratings', distinct=True),
                num_guests=Coalesce(
                    Subquery(
                        detail_values.filter(property_group_detail__detail__slug='maxGuests').values('integer_value')[
                            :1
                        ],
                        output_field=IntegerField(),
                    ),
                    Value(0),
                ),
                curator=Coalesce(
                    Subquery(
                        detail_values.filter(property_group_detail__detail__slug='curator').values('text_value')[:1],
                        output_field=CharField(),
                    ),
                    Value(''),
                ),
                bedbath=Coalesce(
                    Subquery(
                        detail_values.filter(property_group_detail__detail__slug='bedbath').values('description_value')[
                            :1
                        ],
                        output_field=CharField(),
                    ),
                    Value(''),
                ),
                num_bedrooms=Coalesce(
                    Subquery(room_counts.values('bedroom_count')[:1]),
                    Value(0),
                    output_field=IntegerField(),
                ),
                num_bathrooms=Coalesce(
                    Subquery(room_counts.values('bathroom_count')[:1]),
                    Value(0),
                    output_field=IntegerField(),
                ),
                design_type=Coalesce(
                    Subquery(
                        detail_values.filter(property_group_detail__detail__slug='designType').values(
                            'detail_option__name'
                        )[:1],
                        output_field=CharField(),
                    ),
                    Value(''),
                ),
                special_offer_line=Value('', output_field=CharField()),
            )
        )

        property_obj = property_qs.first()
        if not property_obj:
            return None

        return BasePropertySerializer(property_obj).data
