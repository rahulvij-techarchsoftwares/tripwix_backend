import json
from typing import Any

from django.core.management.base import BaseCommand

from apps.properties.import_bathroom import ImportBathRooms


class Command(BaseCommand):
    def handle(self, *args: Any, **options: Any) -> str | None:

        try:
            with open('docs/bathrooms.json') as file:
                object_list = json.load(file)
                import_tripwix = ImportBathRooms(object_list)
                import_tripwix.run()
        except FileNotFoundError:
            return None
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")

        return "Saved"
