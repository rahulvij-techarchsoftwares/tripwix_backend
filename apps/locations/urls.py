from django.urls import path

from apps.locations.views import city_options, community_options, country_options, destination_options

urlpatterns = [
    path('city_options/', city_options, name='city_options'),
    path('community_options/', community_options, name='community_options'),
    path('country_options/', country_options, name='country_options'),
    path('destination_options/', destination_options, name='destination_options'),
]
