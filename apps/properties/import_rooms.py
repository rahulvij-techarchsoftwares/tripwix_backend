from django.db import transaction

from apps.properties.models import Property, PropertyBedroomsConfig, PropertyDivision, PropertyDivisionExtra


class ImportRooms(object):
    properties_map = {}

    def __init__(self, rooms) -> None:
        self.rooms = rooms

    def get_create_room(self, room):
        if room.get('propertyid') not in self.properties_map:
            self.properties_map[room.get('propertyid')] = Property.objects.get(reference=room.get('propertyid'))
        room_obj, created = PropertyDivision.objects.get_or_create(
            property_object=self.properties_map[room.get('propertyid')],
            name=room.get('bedroomDesc'),
            defaults=dict(division_type_id=1, name=room.get('bedroomDesc')),
        )
        extra = PropertyDivisionExtra.objects.get(id=room.get('extra'))
        room_obj.extra.add(extra)
        if created:
            PropertyBedroomsConfig.objects.create(
                property_object=self.properties_map[room.get('propertyid')],
                division=room_obj,
                bed_type_id=room.get('bedType'),
                number=room.get('bedQuantity'),
            )
        return room_obj

    def run(self):
        with transaction.atomic():
            for room in self.rooms:
                self.get_create_room(room)

        return True
