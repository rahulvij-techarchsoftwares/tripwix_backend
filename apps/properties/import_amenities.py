from django.db import transaction
from django.utils.text import slugify

from apps.properties.models import Amenity, Property


class ImportAmenities(object):
    amenities_map = {}
    properties_map = {}

    def __init__(self, amenities) -> None:
        self.amenities = amenities

    def get_create_amenity(self, amenity):
        if slugify(amenity.get('name')) not in self.amenities_map:
            amenity_obj, created = Amenity.objects.get_or_create(
                slug=slugify(amenity.get('name')),
                defaults=dict(name=amenity.get('name'), category_id=amenity.get('category')),
            )
            if created:
                self.amenities_map[amenity_obj.slug] = amenity_obj
        else:
            amenity_obj = self.amenities_map[slugify(amenity.get('name'))]
        return amenity_obj

    def run(self):
        with transaction.atomic():
            for amenity in self.amenities:
                if amenity.get('propertyid') not in self.properties_map:
                    self.properties_map[amenity.get('propertyid')] = Property.objects.get(
                        reference=amenity.get('propertyid')
                    )
                amenity_obj = self.get_create_amenity(amenity)
                self.properties_map[amenity.get('propertyid')].amenities.add(amenity_obj)

        return True
