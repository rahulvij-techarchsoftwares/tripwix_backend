import json
from typing import Any

from django.core.management.base import BaseCommand

from apps.properties.import_tripwix import ImportPropertiesTripWix


class Command(BaseCommand):
    def handle(self, *args: Any, **options: Any) -> str | None:
        try:
            with open("docs/properties.json") as file:
                properties_list = json.load(file)
                print("Read file")
        except FileNotFoundError:
            return None
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")

        import_prop_tripwix = ImportPropertiesTripWix(properties=properties_list)
        import_prop_tripwix.run(import_photos=True)

        return "Saved"
