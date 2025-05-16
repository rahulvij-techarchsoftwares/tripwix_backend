from django.http import JsonResponse
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_GET

from apps.locations.models import City, Country, Location, SubLocation


@require_GET
@cache_page(60 * 5, key_prefix="locations")
def country_options(request):
    """
    Return a list of countries
    """

    country_options = list(Country.objects.values('alpha2', 'name').distinct().order_by('name'))
    return JsonResponse(country_options, safe=False)


@require_GET
@cache_page(60 * 5, key_prefix="locations")
def city_options(request):
    """
    Filter cities by Alpha2 country code (e.g. 'US' for United States)
    """

    raw_country = request.GET.get('country')
    if not isinstance(raw_country, str):
        return JsonResponse([], safe=False)
    if not raw_country:
        return JsonResponse([], safe=False)
    country = raw_country[:2]
    city_options = list(City.objects.filter(country__alpha2=country).values('id', 'name').order_by('name'))
    return JsonResponse(city_options, safe=False)


@require_GET
@cache_page(60 * 5, key_prefix="locations")
def destination_options(request):
    """
    Filter destinations by Alpha2 country code (e.g. 'US' for United States)
    """

    raw_country = request.GET.get('country')
    raw_city = request.GET.get('city')
    if not raw_country and not raw_city:
        return JsonResponse([], safe=False)
    if (raw_country and not isinstance(raw_country, str)) or (raw_city and not isinstance(raw_city, str)):
        return JsonResponse([], safe=False)
    if raw_country:
        country = raw_country[:2]
        destination_options = list(
            Location.objects.filter(country__alpha2=country).values('id', 'name').order_by('name')
        )
    elif raw_city:
        destination_options = list(Location.objects.filter(
            cities__id=int(raw_city)).values('id', 'name').order_by('name'))
    return JsonResponse(destination_options, safe=False)


@require_GET
@cache_page(60 * 5, key_prefix="locations")
def community_options(request):
    """
    Filter communities by destination ID
    """

    raw_destination = request.GET.get('destination')
    try:
        destination = int(raw_destination)
    except Exception:
        return JsonResponse([], safe=False)
    community_options = list(SubLocation.objects.filter(location__id=destination).values('id', 'name').order_by('name'))
    return JsonResponse(community_options, safe=False)
