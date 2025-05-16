from django.urls import path, re_path

from .views import (
    ImportAmenitiesView,
    ImportOwnersView,
    ImportPropertiesView,
    ImportRatesView,
    get_property_active_amenities,
    update_property_active_amenities,
    
)


urlpatterns = [
    re_path('admin/import-owners/$', ImportOwnersView.as_view(), name='import-owners'),
    re_path('admin/import-properties/$', ImportPropertiesView.as_view(), name='import-properties'),
    re_path('admin/import-amenities/$', ImportAmenitiesView.as_view(), name='import-amenities'),
    re_path('admin/import-rates/$', ImportRatesView.as_view(), name='import-rates'),
    path(
        'update_property_active_amenities/', update_property_active_amenities, name='update_property_active_amenities'
    ),
    path(
        'get_property_active_amenities/<int:property_id>/',
        get_property_active_amenities,
        name='get_property_active_amenities',
    ),
]
