from typing import Any

from django.core.management.base import BaseCommand
from django.db.models import F, Func, JSONField, Value
from django.db.models.functions import Concat

from apps.properties.models import Detail, PropertyDetailValues


class Command(BaseCommand):
    def handle(self, *args: Any, **options: Any) -> str | None:
        details_to_update = Detail.objects.filter(detail_type="number_with_value_type_selector").values_list(
            "pk", flat=True
        )

        if len(details_to_update) == 0:
            return "Detail not found"

        updated_details = (
            PropertyDetailValues.objects.select_related("property_group_detail")
            .filter(property_group_detail__detail_id__in=details_to_update)
            .exclude(text_value__icontains="value_type")
            .annotate(
                fixed_value=Func(
                    Value("value"),
                    F("text_value"),
                    Value("value_type"),
                    Value(""),
                    function="jsonb_build_object",
                    output_field=JSONField(),
                ),
            )
            .update(text_value=F("fixed_value"))
        )

        return f"Fixed {updated_details} detail values"
