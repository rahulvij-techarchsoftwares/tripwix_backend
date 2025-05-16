import json
from typing import Any

from django.core.management.base import BaseCommand

from apps.properties.import_owners import ImportOwnersTripWix


class Command(BaseCommand):
    def handle(self, *args: Any, **options: Any) -> str | None:
        import_owners_tripwix = ImportOwnersTripWix()
        try:
            with open('docs/accounts.json') as file:
                owners_list = json.load(file)
                import_owners_tripwix.run(owners_list)
        except FileNotFoundError:
            return None
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")

        return "Saved"
