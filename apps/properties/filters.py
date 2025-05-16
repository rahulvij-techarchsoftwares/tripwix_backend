from django.db.models import Case, CharField, Count, F, IntegerField, OuterRef, Q, Subquery, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone
from django_filters import rest_framework as filters

from .models import Amenity, DetailOption, Property, PropertyDetailValues, PropertyType, Rate


class PropertyFilter(filters.FilterSet):
    country = filters.CharFilter(method='filter_country', label='Country Alpha2 Code')
    destination = filters.NumberFilter(method='filter_destination', label='Destination ID')
    community = filters.NumberFilter(method='filter_community', label='Community ID')
    category = filters.ModelMultipleChoiceFilter(
        queryset=PropertyType.objects.all(), field_name='property_type__slug', to_field_name='slug'
    )
    price = filters.RangeFilter(method='filter_price')
    num_guests = filters.NumberFilter(method='filter_num_guests', label='Number of Guests')
    num_bedrooms = filters.NumberFilter(method='filter_num_bedrooms', label='Number of Bedrooms')
    num_bathrooms = filters.NumberFilter(method='filter_num_bathrooms', label='Number of Bathrooms')
    amenities = filters.ModelMultipleChoiceFilter(
        queryset=Amenity.objects.all(), field_name='amenities__slug', to_field_name='slug'
    )
    instant_booking = filters.BooleanFilter(method='filter_instant_booking')
    special_offer = filters.BooleanFilter(method='filter_special_offer')
    lifestyle = filters.CharFilter(method='filter_lifestyle')
    acessibility = filters.CharFilter(method='filter_acessibility')
    design_types = filters.ModelMultipleChoiceFilter(
        method='filter_design_types',
        queryset=DetailOption.objects.filter(detail__slug='designType'),
        field_name="slug",
        to_field_name="slug",
    )
    order_by = filters.CharFilter(
        method='filter_order_by',
        label="""
            Order by:
            - price-asc
            - price-desc
            - name-asc
            - name-desc
            - recommended
        """,
    )
    available_at = filters.DateFromToRangeFilter(
        method='filter_available_at',
        label='Available At (available_at_after [initial date], available_at_before [end date])',
    )

    class Meta:
        model = Property
        fields = (
            'country',
            'destination',
            'community',
            'category',
            'price',
            'num_guests',
            'num_bedrooms',
            'num_bathrooms',
            'amenities',
            'instant_booking',
            'special_offer',
            'lifestyle',
            'acessibility',
            "order_by",
            'available_at',
        )

    def filter_design_types(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(detail_values__detail_option__in=value)

    def filter_country(self, queryset, name, value):
        country_values = self.request.GET.getlist('country')
        if not country_values:
            return queryset

        return queryset.filter(location__country__alpha2__in=country_values)

    def filter_destination(self, queryset, name, value):
        destination_values = self.request.GET.getlist('destination')
        if not destination_values:
            return queryset

        return queryset.filter(location__id__in=destination_values)

    def filter_community(self, queryset, name, value):
        community_values = self.request.GET.getlist('community')
        if not community_values:
            return queryset

        return queryset.filter(sublocation__id__in=community_values)

    def filter_price(self, queryset, name, value):
        if not value:
            return queryset
        min_price, max_price = value.start, value.stop
        rates_queryset = Rate.objects.filter(property=OuterRef('pk'))
        queryset = queryset.annotate(
            min_rate=Subquery(
                rates_queryset.values('website_sales_value').order_by('website_sales_value')[:1],
                output_field=IntegerField(),
            )
        )
        if min_price is not None:
            queryset = queryset.filter(min_rate__gte=min_price)
        if max_price is not None:
            queryset = queryset.filter(min_rate__lte=max_price)
        return queryset

    def filter_instant_booking(self, queryset, name, value):
        return queryset.filter(
            detail_values__bool_value=value, detail_values__property_group_detail__detail__slug='instantBooking'
        )

    def filter_num_guests(self, queryset, name, value):
        queryset = queryset.annotate(
            num_guests=Subquery(
                PropertyDetailValues.objects.filter(
                    property_object=OuterRef('pk'), property_group_detail__detail__slug='maxGuests'
                ).values('integer_value')[:1],
                output_field=IntegerField(),
            )
        ).filter(num_guests__gte=value)
        return queryset

    def filter_num_bedrooms(self, queryset, name, value):
        queryset = queryset.annotate(
            num_bedrooms=Count("divisions", filter=Q(divisions__division_type__slug='bedroom'), distinct=True)
        ).filter(num_bedrooms__gte=value)
        return queryset

    def filter_num_bathrooms(self, queryset, name, value):
        queryset = queryset.annotate(
            num_bathrooms=Count(
                "divisions",
                filter=(Q(divisions__division_type__slug='bathroom') | Q(divisions__extra__id__in=[1, 2, 3, 6])),
                distinct=True,
            )
        ).filter(num_bathrooms__gte=value)
        return queryset

    def filter_special_offer(self, queryset, name, value):
        if not value:
            return queryset

        today = timezone.now().date()

        featured_subquery = (
            PropertyDetailValues.objects.filter(
                property_object=OuterRef('id'), property_group_detail__detail__slug='specialOfferFeatured'
            )
            .values('bool_value')
            .order_by('bool_value')[:1]
        )

        queryset = (
            queryset.annotate(special_offer_featured=Coalesce(Subquery(featured_subquery), Value(False)))
            .filter(Q(special_offer_start_date__lte=today) & Q(special_offer_end_date__gte=today))
            .order_by('-special_offer_featured')
        )

        return queryset

    def filter_lifestyle(self, queryset, name, value):
        lifestyle_values = self.request.GET.getlist('lifestyle')
        if not lifestyle_values:
            return queryset

        queryset = queryset.annotate(
            lifestyle=Coalesce(
                Case(
                    When(
                        detail_values__property_group_detail__detail__slug='perfectFor',
                        then=F('detail_values__detail_option__slug'),
                    ),
                    default=Value(None),
                    output_field=CharField(),
                ),
                Value(None),
            )
        ).filter(lifestyle__in=lifestyle_values)
        return queryset

    def filter_acessibility(self, queryset, name, value):
        accessibility_values = self.request.GET.getlist('acessibility')
        if not accessibility_values:
            return queryset
        queryset = queryset.annotate(
            suitable_for_families=Subquery(
                queryset.filter(
                    pk=OuterRef('pk'),
                    detail_values__property_group_detail__detail__slug='adultsOnlyHouse',
                )
                .values('pk')
                .annotate(result=F('detail_values__detail_option__slug'))
                .values('result')[:1]
            ),
            suitable_for_pets=Subquery(
                queryset.filter(
                    pk=OuterRef('pk'),
                    detail_values__property_group_detail__detail__slug='petsOnRequest',
                )
                .values('pk')
                .annotate(result=F('detail_values__detail_option__slug'))
                .values('result')[:1]
            ),
            suitable_for_events=Subquery(
                queryset.filter(
                    pk=OuterRef('pk'),
                    detail_values__property_group_detail__detail__slug='partiesEvents',
                )
                .values('pk')
                .annotate(result=F('detail_values__detail_option__slug'))
                .values('result')[:1]
            ),
        )

        q = Q()
        if 'suitable-for-families' in accessibility_values:
            q &= Q(suitable_for_families='families-allowed')
        if 'pet-friendly' in accessibility_values:
            q &= Q(suitable_for_pets__in=['pets-on-request', 'pets-allowed'])
        if 'events' in accessibility_values:
            q &= Q(
                suitable_for_events__in=[
                    'allowed',
                    'on-request',
                    'parties-events-on-request',
                    'parties-events-allows',
                    'parties-events-allows-upto-10pm',
                ]
            )

        queryset = queryset.filter(q)
        return queryset

    def filter_order_by(self, queryset, name, value):
        if value == 'price-asc':
            rates_queryset = Rate.objects.filter(property=OuterRef('pk'))
            return (
                queryset.annotate(
                    min_rate=Subquery(
                        rates_queryset.values('website_sales_value').order_by('website_sales_value')[:1],
                        output_field=IntegerField(),
                    )
                )
                .order_by('min_rate')
                .distinct()
            )
        elif value == 'price-desc':
            rates_queryset = Rate.objects.filter(property=OuterRef('pk'))
            return (
                queryset.annotate(
                    min_rate=Subquery(
                        rates_queryset.values('website_sales_value').order_by('website_sales_value')[:1],
                        output_field=IntegerField(),
                    )
                )
                .order_by('-min_rate')
                .distinct()
            )
        elif value == "name-asc":
            return queryset.order_by('tagline_or_title')
        elif value == "name-desc":
            return queryset.order_by('-tagline_or_title')
        elif value == "recommended":
            return queryset.order_by("-is_featured")
        return queryset

    def filter_available_at(self, queryset, name, value):
        if not value:
            return queryset

        if value.start is not None and value.stop is not None:
            lookup_expr = "range"
            value = (value.start, value.stop)
        elif value.start is not None:
            lookup_expr = "gte"
            value = value.start
        elif value.stop is not None:
            lookup_expr = "lte"
            value = value.stop

        filter_kwargs = {f"hostify_calendars__date__{lookup_expr}": value, "hostify_calendars__status": "available"}
        queryset = queryset.filter(**filter_kwargs).distinct()
        return queryset
