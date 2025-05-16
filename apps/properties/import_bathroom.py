from django.db import transaction

from apps.properties.models import Property, PropertyBedroomsConfig, PropertyDivision, PropertyDivisionExtra


class ImportBathRooms(object):
    properties_map = {}

    def __init__(self, bathrooms) -> None:
        self.bathrooms = bathrooms

    def get_create_bathroom(self, bathroom):
        if bathroom.get('propertyid') not in self.properties_map:
            self.properties_map[bathroom.get('propertyid')] = Property.objects.get(reference=bathroom.get('propertyid'))
        bathroom_obj, created = PropertyDivision.objects.get_or_create(
            property_object=self.properties_map[bathroom.get('propertyid')],
            name=bathroom.get('bathroomDesc'),
            defaults=dict(division_type_id=9, name=bathroom.get('bathroomDesc')),
        )
        extra = PropertyDivisionExtra.objects.get(id=bathroom.get('extra'))
        bathroom_obj.extra.add(extra)
        return bathroom_obj

    def run(self):
        with transaction.atomic():
            for bathroom in self.bathrooms:
                self.get_create_bathroom(bathroom)

        return True
