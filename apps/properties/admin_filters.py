from datetime import datetime, timedelta

from django.contrib.admin import FieldListFilter, SimpleListFilter
from django.db.models import Count, OuterRef, Q, Subquery
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.hostify.constants import CalendarStatusChoices
from apps.locations.models import Location, SubLocation
from apps.properties.models import Property, PropertyDetailValues, PropertyDivision


class BasePropertyConfigFilter(SimpleListFilter):
    """
    This class intends to make all lookups dependent on the current queryset.
    """

    def has_output(self):
        return True

    def _filtered_query_dict(self, request):
        allowed_filters = {
            'is_active__exact',
            'location',
            'max_guests',
            'property_type',
            'sublocation',
            'typology',
            'num_bedrooms',
        }

        return {k: v for k, v in request.GET.dict().items() if k in allowed_filters and isinstance(v, int)}

    def _process_q_param(self, q_param: str):
        if not q_param:
            return Q()
        q_param = str(q_param)
        filtering = Q()
        filtering |= Q(name__icontains=q_param)
        filtering |= Q(title__icontains=q_param)
        filtering |= Q(reference__icontains=q_param)
        filtering |= Q(address__icontains=q_param)
        return filtering

    def _get_property_annotated_queryset(self, request, queryset=None):
        if not queryset:
            queryset = Property.objects.all()
        if request.GET.get("q"):
            queryset = queryset.filter(self._process_q_param(request.GET.get("q")))
        if request.GET.get("is_active__exact"):
            queryset = queryset.filter(
                Q(is_active=True)
                & Q(
                    Q(publication_date__lte=timezone.now()) | Q(publication_date__isnull=True),
                    Q(publication_end_date__gt=timezone.now()) | Q(publication_end_date__isnull=True),
                ),
            )
        return queryset.annotate(
            num_bedrooms=Subquery(
                PropertyDivision.objects.filter(property_object=OuterRef("pk"), division_type__slug="bedroom")
                .values("property_object")
                .annotate(count=Count("pk"))
                .values("count")
            ),
            max_guests=Subquery(
                PropertyDetailValues.objects.filter(
                    property_object=OuterRef("pk"), property_group_detail__detail__slug="maxGuests"
                ).values("integer_value")[:1]
            ),
        )


class PropertyBedroomsConfigFilter(BasePropertyConfigFilter):
    title = _("Bedroom count")
    parameter_name = "num_bedrooms"

    def lookups(self, request, *args, **kwargs):
        queryset = self._get_property_annotated_queryset(request)
        num_bedrooms = (
            queryset.filter(**{'num_bedrooms__isnull': False, **self._filtered_query_dict(request)})
            .distinct('num_bedrooms')
            .order_by("num_bedrooms")
            .values_list("num_bedrooms", flat=True)
            or []
        )
        return [(str(i), str(i)) for i in num_bedrooms]

    def queryset(self, request, queryset):
        try:
            if self.value:
                queryset = (
                    self._get_property_annotated_queryset(request, queryset)
                    .distinct()
                    .filter(num_bedrooms=int(self.value()))
                )
        except (TypeError, ValueError):
            pass
        return queryset


class LocationConfigFilter(BasePropertyConfigFilter):
    title = _("Destination")
    parameter_name = "location"

    def lookups(self, request, model_admin):
        properties = (
            self._get_property_annotated_queryset(request)
            .filter(**self._filtered_query_dict(request))
            .values_list("id", flat=True)
        )
        return Location.objects.filter(property__id__in=properties).distinct().values_list("id", "name")

    def queryset(self, request, queryset):
        try:
            if self.value():
                return queryset.filter(location__id=int(self.value()))
        except (TypeError, ValueError):
            pass
        return queryset


class CommunityConfigFilter(BasePropertyConfigFilter):
    title = _("Community")
    parameter_name = "sublocation"

    def lookups(self, request, model_admin):
        properties = (
            self._get_property_annotated_queryset(request)
            .filter(**self._filtered_query_dict(request))
            .values_list("id", flat=True)
        )
        return SubLocation.objects.filter(property__id__in=properties).distinct().values_list("id", "name")

    def queryset(self, request, queryset):
        try:
            if self.value():
                return queryset.filter(sublocation__id=int(self.value()))
        except (TypeError, ValueError):
            pass
        return queryset


class MaxGuestsConfigFilter(BasePropertyConfigFilter):
    title = _("Max guests")
    parameter_name = "max_guests"

    def lookups(self, request, model_admin):
        return [
            (str(i), str(i))
            for i in self._get_property_annotated_queryset(request)
            .filter(**{'max_guests__isnull': False, **self._filtered_query_dict(request)})
            .distinct()
            .values_list("max_guests", flat=True)
        ]

    def queryset(self, request, queryset):
        try:
            if self.value():
                return self._get_property_annotated_queryset(request, queryset).filter(max_guests=int(self.value()))
        except (TypeError, ValueError):
            pass
        return queryset


class PropertyTypeConfigFilter(BasePropertyConfigFilter):
    title = _("Property type")
    parameter_name = "property_type"

    def lookups(self, request, model_admin):
        return [
            (str(p_type_id), str(p_type_name))
            for p_type_id, p_type_name in self._get_property_annotated_queryset(request)
            .filter(**self._filtered_query_dict(request))
            .distinct()
            .order_by("property_type__name")
            .values_list("property_type__id", "property_type__name")
        ]

    def queryset(self, request, queryset):
        try:
            if self.value():
                return self._get_property_annotated_queryset(request, queryset).filter(property_type=int(self.value()))
        except (TypeError, ValueError):
            pass
        return queryset


class TypologyConfigFilter(BasePropertyConfigFilter):
    title = _("Typology")
    parameter_name = "typology"

    def lookups(self, request, model_admin):
        return [
            (str(t_id), str(t_name))
            for t_id, t_name in self._get_property_annotated_queryset(request)
            .filter(**self._filtered_query_dict(request))
            .distinct()
            .order_by("typology__name")
            .values_list("typology__id", "typology__name")
        ]

    def queryset(self, request, queryset):
        try:
            if self.value():
                return self._get_property_annotated_queryset(request, queryset).filter(typology=int(self.value()))
        except (TypeError, ValueError):
            pass
        return queryset


class DateRangeFilter(FieldListFilter):
    title = _('Date Range')
    parameter_name = 'start_date'
    template = 'admin/date_range_filter.html'
    lookup_val = None
    lookup_choices = []

    def __init__(self, field, request, params, model, model_admin, field_path):
        super().__init__(field, request, params, model, model_admin, field_path)
        self.request = request

    def expected_parameters(self):
        return ['start_date', 'end_date']

    def choices(self, changelist):
        yield {
            'selected': self.lookup_val is None,
            'query_string': changelist.get_query_string(remove=[self.parameter_name, 'end_date']),
            'display': _('All'),
        }

        for lookup, title in self.lookup_choices:
            yield {
                'selected': self.lookup_val == str(lookup),
                'query_string': changelist.get_query_string({self.parameter_name: lookup}),
                'display': title,
            }

    def lookups(self, request, model_admin):
        return []

    def queryset(self, request, queryset):
        if 'start_date' in request.GET or 'end_date' in request.GET:
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')

            if start_date or end_date:
                date_range_array = []
                if start_date and end_date:
                    start_date = datetime.strptime(start_date, '%Y-%m-%d')
                    end_date = datetime.strptime(end_date, '%Y-%m-%d')
                    date_range_array = [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]
                elif start_date:
                    start_date = datetime.strptime(start_date, '%Y-%m-%d')
                    date_range_array = [start_date]
                elif end_date:
                    end_date = datetime.strptime(end_date, '%Y-%m-%d')
                    date_range_array = [end_date]

                queryset = queryset.filter(
                    hostify_calendars__date__in=date_range_array,
                    hostify_calendars__status=CalendarStatusChoices.AVAILABLE,
                )
        return queryset
