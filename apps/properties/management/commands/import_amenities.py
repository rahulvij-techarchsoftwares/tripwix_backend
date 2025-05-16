import json
from typing import Any

from django.core.management.base import BaseCommand

from apps.properties.import_amenities import ImportAmenities


class Command(BaseCommand):
    def handle(self, *args: Any, **options: Any) -> str | None:

        try:
            with open('docs/amenities.json') as file:
                object_list = json.load(file)
                import_tripwix = ImportAmenities(object_list)
                import_tripwix.run()
        except FileNotFoundError:
            return None
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")

        return "Saved"
