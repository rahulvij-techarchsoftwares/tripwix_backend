from collections import namedtuple
from datetime import datetime

import pytz
from django.conf import settings
from django.contrib.postgres.aggregates import ArrayAgg
from django.db.models import (
    Avg,
    BooleanField,
    Case,
    CharField,
    Count,
    DateField,
    F,
    IntegerField,
    Max,
    Min,
    OuterRef,
    Prefetch,
    Q,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Coalesce, Concat
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_api_key.permissions import HasAPIKey

from apps.hostify.tasks import task_process_calendar_webhook
from apps.locations.models import Location, SubLocation
from apps.pages.models import Page
from apps.properties.filters import PropertyFilter
from apps.properties.models import (
    Ambassador,
    Amenity,
    DetailOption,
    Property,
    PropertyAmenity,
    PropertyBedroomsConfig,
    PropertyBedroomsConfigBedType,
    PropertyDetailValues,
    PropertyMediaPhoto,
    PropertyRatingScore,
    PropertyType,
    Rate,
    Wishlist,
)
from apps.properties.utils import ExchangeRateService
from apps.tools.google_drive_api import GoogleDriveApi, GoogleSheetsAPI

from ..import_tripwix import ImportPropertiesTripWix
from ..utils import PropertyBuilder
from .serializers import (
    AmbassadorSerializer,
    BasePropertySerializer,
    FeeAndAvailabilitySerializer,
    GoogleAPINotificationSerializer,
    HostifyWebhookSerializer,
    PropertyDetailSerializer,
    PropertyFilterSerializer,
    PropertySerializer,
    WishlistSerializer,
)

utc = pytz.UTC


class GoogleAPINotificationView(generics.CreateAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = GoogleAPINotificationSerializer

    @staticmethod
    def clear_sheets_properties(data, properties):
        rows_number = data[0].split("\t")
        rows = ["" for row in rows_number]

        range_name = f"2:{2 + len(properties)}"
        values = [rows for prop in properties]
        GoogleSheetsAPI().update_google_sheet_file(range_name, values)

    def post(self, request, *args, **kwargs):
        token_str = request.META.get("HTTP_X_GOOG_CHANNEL_TOKEN", None)

        if token_str is None:
            return Response({"status": "Failed", "details": "No token"})

        now = timezone.now()
        token = datetime.strptime(token_str, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=utc)
        expiration = (now - timezone.timedelta(minutes=5)).replace(tzinfo=utc)

        if token < expiration:  # token expired
            return Response({"status": "Failed", "details": "Expired Token"})

        google_drive = GoogleDriveApi()
        changes = google_drive.get_google_drive_changes()

        for change in changes:
            if change.get("fileId") == settings.UPDATE_FILE_ID:
                data = google_drive.get_google_sheet_file(settings.UPDATE_FILE_ID)
                properties = PropertyBuilder().build(data)
                import_prop_tripwix = ImportPropertiesTripWix(properties=properties)
                import_prop_tripwix.run(import_photos=True)

                self.clear_sheets_properties(data, properties)

        return Response({"status": "OK"})


class PropertyCalendarWebhookView(generics.CreateAPIView):
    serializer_class = HostifyWebhookSerializer

    permission_classes = (HasAPIKey,)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task_process_calendar_webhook.delay(serializer.data)
        return Response(status=204)


class AmbassadorViewSet(viewsets.ModelViewSet):
    queryset = Ambassador.objects.all()
    serializer_class = AmbassadorSerializer


class PropertyViewSet(viewsets.GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    serializer_class = PropertySerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = PropertyFilter
    ordering_fields = ('title', 'price')

    def get_queryset(self):
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

        detail_values = PropertyDetailValues.objects.prefetch_related(
            'property_group_detail', 'property_group_detail__detail'
        ).filter(property_object=OuterRef('pk'))

        qs = (
            Property.objects.published()
            .prefetch_related(
                Prefetch('ratings', queryset=PropertyRatingScore.objects.only('score', 'id', 'property_object_id')),
                Prefetch('photos', queryset=PropertyMediaPhoto.objects.only('image', 'caption')),
                Prefetch(
                    'rates',
                    queryset=Rate.objects.filter(Q(Q(from_date__gte=now) | Q(to_date__gte=now))).only(
                        'id', 'property_id', 'website_sales_value', 'minimum_nights'
                    ),
                ),
                Prefetch(
                    'property_amenities__amenity',
                    queryset=PropertyAmenity.objects.only(
                        'id', 'property_id', 'amenity__id', 'amenity__name', 'amenity__slug'
                    ),
                ),
                Prefetch(
                    'location',
                    queryset=Location.objects.only(
                        'id',
                        'name',
                        'slug',
                        'country_id',
                        'country__name',
                        'country__alpha2',
                        'country__alpha3',
                        'country__numcode',
                        'country__phone',
                    ),
                ),
                Prefetch('sublocation', queryset=SubLocation.objects.only('id', 'name', 'image')),
                'property_group',
            )
            .annotate(
                destination_slug=Concat(Value("destinations/"), F("location__slug"), output_field=CharField()),
                page_exists=Subquery(
                    Page.objects.filter(slug=OuterRef("destination_slug"), is_active=True).values("pk")[:1]
                ),
                location_slug_annotated=Case(
                    When(page_exists__isnull=False, then=F("location__slug")),
                    default=Value(""),
                    output_field=CharField(),
                ),
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
                    Value(""),
                ),
                bedbath=Coalesce(
                    Subquery(
                        detail_values.filter(property_group_detail__detail__slug='bedbath').values('description_value')[
                            :1
                        ],
                        output_field=CharField(),
                    ),
                    Value(""),
                ),
                num_bedrooms=Coalesce(
                    Subquery(
                        room_counts.values('bedroom_count')[:1],
                        output_field=IntegerField(),
                    ),
                    Value(0),
                ),
                num_bathrooms=Coalesce(
                    Subquery(
                        room_counts.values('bathroom_count')[:1],
                        output_field=IntegerField(),
                    ),
                    Value(0),
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
                special_offer_start_date=Subquery(
                    detail_values.filter(property_group_detail__detail__slug='offerStartDate')
                    .values('date_value')
                    .order_by('date_value')[:1],
                    output_field=DateField(),
                ),
                special_offer_end_date=Subquery(
                    detail_values.filter(property_group_detail__detail__slug='offerEndDate')
                    .values('date_value')
                    .order_by('date_value')[:1],
                    output_field=DateField(),
                ),
                is_special_offer_active=Case(
                    When(
                        Q(special_offer_start_date__lte=today) & Q(special_offer_end_date__gte=today),
                        then=Value(True),
                    ),
                    default=Value(False),
                    output_field=BooleanField(),
                ),
                special_offer_line=Case(
                    When(
                        is_special_offer_active=True,
                        then=Subquery(
                            detail_values.filter(property_group_detail__detail__slug='specialOfferLine').values(
                                'text_value'
                            )[:1],
                            output_field=CharField(),
                        ),
                    ),
                    default=Value(''),
                    output_field=CharField(),
                ),
                tagline_or_title=Case(
                    When(Q(tagline='') | Q(tagline__isnull=True), then=F('title')),
                    default=F('tagline'),
                    output_field=CharField(),
                ),
            )
        )
        if self.action in ('retrieve', 'slug'):
            qs = (
                qs.prefetch_related(
                    Prefetch(
                        'bedrooms_configurations',
                        PropertyBedroomsConfig.objects.only(
                            'id',
                            'property_object_id',
                            'division__name',
                            'bed_type',
                            'bed_type__id',
                            'bed_type__name',
                            'number',
                        ),
                    ),
                    Prefetch(
                        'bedrooms_configurations__bed_type',
                        PropertyBedroomsConfigBedType.objects.only('id', 'name', 'slug', 'item_o'),
                    ),
                    Prefetch(
                        'ambassador',
                        Ambassador.objects.only('id', 'name', 'photo', 'description'),
                    ),
                    'amenities',
                )
                .annotate(
                    know_before_you_go_detail=Coalesce(
                        Subquery(
                            detail_values.filter(property_group_detail__detail__slug='knowBeforeYouGo').values(
                                'description_value'
                            )[:1],
                            output_field=CharField(),
                        ),
                        Value(""),
                    ),
                    Location_para=Coalesce(
                        Subquery(
                            detail_values.filter(property_group_detail__detail__slug='location').values(
                                'description_value'
                            )[:1],
                            output_field=CharField(),
                        ),
                        Value(""),
                    ),
                    Living_Areas=Coalesce(
                        Subquery(
                            detail_values.filter(property_group_detail__detail__slug='livingAreas').values(
                                'description_value'
                            )[:1],
                            output_field=CharField(),
                        ),
                        Value(""),
                    ),
                    Special_Features=Coalesce(
                        Subquery(
                            detail_values.filter(property_group_detail__detail__slug='specialFeatures').values(
                                'description_value'
                            )[:1],
                            output_field=CharField(),
                        ),
                        Value(""),
                    ),
                    location_Description=Coalesce(
                        Subquery(
                            detail_values.filter(property_group_detail__detail__slug='locationDescription').values(
                                'description_value'
                            )[:1],
                            output_field=CharField(),
                        ),
                        Value(""),
                    ),
                    location_extra=Coalesce(
                        Subquery(
                            detail_values.filter(property_group_detail__detail__slug='location').values(
                                'description_value'
                            )[:1],
                            output_field=CharField(),
                        ),
                        Value(""),
                    ),
                    rental_price_included_detail=Coalesce(
                        Subquery(
                            detail_values.filter(property_group_detail__detail__slug='rentalPriceIncludes').values(
                                'description_value'
                            )[:1],
                            output_field=CharField(),
                        ),
                        Value(""),
                    ),
                    special_offer_description=Coalesce(
                        Subquery(
                            detail_values.filter(property_group_detail__detail__slug='specials-promotions').values(
                                'description_value'
                            )[:1],
                            output_field=CharField(),
                        ),
                        Value(""),
                    ),
                    yt_video_url=Subquery(
                        detail_values.filter(property_group_detail__detail__slug='youtubeLink').values('text_value')[
                            :1
                        ],
                        output_field=CharField(),
                    ),
                    tripwix_video_url=Subquery(
                        detail_values.filter(property_group_detail__detail__slug='twVideoLink').values('text_value')[
                            :1
                        ],
                        output_field=CharField(),
                    ),
                    owner_video_url=Subquery(
                        detail_values.filter(property_group_detail__detail__slug='ownerVideoLink').values('text_value')[
                            :1
                        ],
                        output_field=CharField(),
                    ),
                    instant_booking=Subquery(
                        detail_values.filter(property_group_detail__detail__slug='instantBooking').values('bool_value')[
                            :1
                        ],
                        output_field=CharField(),
                    ),
                    minimum_nights=Coalesce(
                        Subquery(
                            Rate.objects.filter(
                                property=OuterRef('pk'),
                                from_date__lte=now,
                                to_date__gte=now,
                            ).values(
                                'minimum_nights'
                            )[:1]
                        ),
                        Value(0),
                    ),
                    active_amenities=ArrayAgg(
                        'property_amenities__amenity',
                        distinct=True,
                    ),
                )
                .only(
                    'id',
                    'slug',
                    'title',
                    'tagline',
                    'hostify_id',
                    'content',
                    'tax_id',
                    'bedrooms_configurations',
                    'ambassador',
                    'default_price_eur',
                    'location',
                    'sublocation',
                    'point',
                    'seo_title',
                    'seo_description',
                )
            )
        else:
            qs = qs.only(
                'id',
                'slug',
                'title',
                'tagline',
                'default_price_eur',
                'location',
                'sublocation',
                'point',
                'seo_title',
                'seo_description',
            )

        return qs.order_by('-item_o')

    def get_serializer_class(self):
        if self.action in ('retrieve', 'slug'):
            return PropertyDetailSerializer
        return BasePropertySerializer

    @action(detail=False, url_path=r'slug/(?P<slug>[/\w\s.-]+)', url_name='property_by_slug', methods=['get'])
    def slug(self, request, slug=None):
        context = {'include': request.GET.get('include', None), 'exclude': request.GET.get('exclude', None)}
        qs = self.get_queryset()
        slug = slug.rstrip('/')
        property_instance = qs.filter(Q(slug=slug) | Q(slug=f'{slug}/')).first()

        if property_instance is None:
            return Response({'detail': 'Property not found'}, status=404)

        return Response(self.get_serializer(property_instance, context=context).data, status=200)

    @action(
        detail=False,
        url_path=r'slug/(?P<slug>[/\w\s.-]+)/fees_and_availability',
        url_name='property_fees_and_availability',
        methods=['get'],
    )
    def fees_and_availability(self, request, slug=None):
        qs = self.get_queryset()
        slug = slug.rstrip('/')
        property_instance = qs.filter(Q(slug=slug) | Q(slug=f'{slug}/')).first()

        if property_instance is None:
            return Response({'detail': 'Property not found'}, status=404)

        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        if not start_date:
            start_date = datetime.strftime(timezone.now().date(), '%Y-%m-%d')
        if not end_date:
            end_date = start_date

        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date() - timezone.timedelta(days=1)

        if end_date < start_date:
            return Response({'detail': 'End date must be greater than start date'}, status=400)

        context = {
            'start_date': start_date,
            'end_date': end_date,
        }

        serializer = FeeAndAvailabilitySerializer(property_instance, context=context)
        return Response(status=200, data=serializer.data)


class PropertyFiltersAPIView(generics.GenericAPIView):
    serializer_class = PropertyFilterSerializer
    permission_classes = (permissions.AllowAny,)

    # @method_decorator(cache_page(600, key_prefix="api_filters"))
    def get(self, request):
        Listing = namedtuple(
            'Listing',
            (
                'countries',
                'num_guests',
                'categories',
                'dates',
                'price_range',
                'num_bedrooms',
                'num_bathrooms',
                'amenities',
                'sort_by',
                'currencies',
                'instant_booking',
                'special_offers',
                'booking_type',
                'lifestyle',
                'acessibilities',
                'design_types',
            ),
        )

        destinations_raw = (
            Location.objects.filter(property__isnull=False, property__is_active=True)
            .distinct()
            .select_related('country')
            .only('id', 'name', 'banner', 'country__name', 'country__alpha2', 'country__banner')
            .order_by('country__alpha2', 'name')
        )
        destinations = {"countries": {}}
        for destination in destinations_raw:
            if destination.country.alpha2 not in destinations['countries']:
                destinations['countries'][destination.country.alpha2] = {
                    'id': destination.country.alpha2,
                    'name': destination.country.name,
                    'banner': destination.country.banner,
                    'destinations': {},
                }
            if destination.id not in destinations['countries'][destination.country.alpha2]['destinations']:
                destinations['countries'][destination.country.alpha2]['destinations'][destination.id] = {
                    'id': destination.id,
                    'name': destination.name,
                    'banner': destination.banner,
                    'communities': {},
                }
                sub_locations = (
                    SubLocation.objects.filter(location=destination.id).distinct().only('id', 'name', 'banner')
                )
                for sub_location in sub_locations:
                    destinations['countries'][destination.country.alpha2]['destinations'][destination.id][
                        'communities'
                    ][sub_location.id] = {
                        'id': sub_location.id,
                        'name': sub_location.name,
                        'banner': sub_location.banner,
                    }

        cleaned_destinations = []
        for country in destinations['countries'].values():
            cleaned_country = {
                'id': country['id'],
                'name': country['name'],
                'banner': country['banner'],
                'destinations': [],
            }
            for destination in country['destinations'].values():
                cleaned_country['destinations'].append(
                    {
                        'id': destination['id'],
                        'name': destination['name'],
                        'banner': destination['banner'],
                        'communities': [
                            {'id': community['id'], 'name': community['name'], 'banner': community['banner']}
                            for community in destination['communities'].values()
                        ],
                    }
                )
            cleaned_destinations.append(cleaned_country)

        properties = Property.objects.filter(is_active=True).annotate(
            num_guests=Subquery(
                PropertyDetailValues.objects.filter(
                    property_object=OuterRef('pk'), property_group_detail__detail__slug='maxGuests'
                ).values('integer_value')[:1],
                output_field=IntegerField(),
            ),
            num_bedrooms=Count("divisions", filter=Q(divisions__division_type__slug='bedroom')),
            num_bathrooms=Count(
                "divisions",
                filter=(Q(divisions__division_type__slug='bathroom')),
            ),
            design_type=Subquery(
                PropertyDetailValues.objects.filter(
                    property_object=OuterRef('pk'), property_group_detail__detail__slug='designType'
                ).values('id', 'detail_option__name')[:1],
                output_field=CharField(),
            ),
        )
        num_guests = list(
            properties.filter(num_guests__isnull=False)
            .values_list('num_guests', flat=True)
            .distinct()
            .order_by('num_guests')
        )
        num_bedrooms = list(
            properties.filter(num_bedrooms__isnull=False)
            .values_list('num_bedrooms', flat=True)
            .distinct()
            .order_by('num_bedrooms')
        )
        num_bathrooms = list(
            properties.filter(num_bathrooms__isnull=False)
            .values_list('num_bathrooms', flat=True)
            .distinct()
            .order_by('num_bathrooms')
        )
        design_types = DetailOption.objects.filter(detail__slug='designType').distinct().values("name", "slug")

        categories = list(PropertyType.objects.filter(property__is_active=True).distinct().values('name', 'slug'))
        price_range = Rate.objects.filter(property__is_active=True, from_date__gte=timezone.now()).aggregate(
            Min('website_sales_value'), Max('website_sales_value')
        )

        amenities = list(Amenity.objects.filter(property__is_active=True).distinct().values('name', 'slug'))
        lifestyle = DetailOption.objects.filter(detail__slug='perfectFor').distinct().values("name", "slug")

        listing = Listing(
            countries=cleaned_destinations,
            num_guests=num_guests,
            categories=categories,
            price_range=price_range,
            num_bedrooms=num_bedrooms,
            num_bathrooms=num_bathrooms,
            amenities=amenities,
            design_types=design_types,
            sort_by=[],
            dates=[],
            instant_booking=[True, False],
            special_offers=[True, False],
            booking_type=[
                {'name': 'Short Term', 'slug': 'short-term'},
                {'name': 'Mid Term', 'slug': 'mid-term'},
                {'name': 'Long Term', 'slug': 'long-term'},
            ],
            lifestyle=lifestyle,
            acessibilities=[
                {'name': 'Suitable for families', 'slug': 'suitable-for-families', 'type': 'boolean'},
                {'name': 'Pet friendly', 'slug': 'pet-friendly', 'type': 'boolean'},
                {'name': 'Events', 'slug': 'events', 'type': 'boolean'},
            ],
            currencies=ExchangeRateService.DESIRED_CURRENCIES,
        )

        response_data = self.serializer_class(listing._asdict()).data

        return Response(response_data, status=status.HTTP_200_OK)


class WishlistViewSet(viewsets.ModelViewSet):
    serializer_class = WishlistSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_queryset(self):
        return Wishlist.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
