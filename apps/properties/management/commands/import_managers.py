import json
from typing import Any

from django.core.management.base import BaseCommand

from apps.properties.import_managers import ImportManagers


class Command(BaseCommand):
    def handle(self, *args: Any, **options: Any) -> str | None:

        try:
            with open('docs/managers.json') as file:
                managers_list = json.load(file)
                import_managers_tripwix = ImportManagers(managers_list)
                import_managers_tripwix.run()
        except FileNotFoundError:
            return None
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")

        return "Saved"
