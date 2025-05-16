import json

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import BadRequest
from django.db import transaction
from django.http.response import HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import generic

from .forms import ImportFileForm
from .import_amenities import ImportAmenities
from .import_owners import ImportOwnersTripWix
from .import_rates import ImportRates
from .import_tripwix import ImportPropertiesTripWix





class ImportTripWixMixin:
    def __init__(self, **kwargs):
        if not settings.ENABLE_BACKOFFICE_IMPORT:
            raise BadRequest("Backoffice Import is not enabled")

        super().__init__(**kwargs)


@method_decorator(staff_member_required, name="dispatch")
class ImportOwnersView(ImportTripWixMixin, generic.FormView):
    template_name = "admin/import_owners.html"
    form_class = ImportFileForm

    @transaction.atomic()
    def post(self, request, *args, **kwargs):
        import_owners = ImportOwnersTripWix()
        owners_file = request.FILES.get("owners")

        if not owners_file.name.endswith(".json"):
            return HttpResponseBadRequest("Only .json file is accepted for accounts upload")

        owners = json.load(owners_file)

        import_owners.run(owners)
        return redirect(reverse_lazy("admin:properties_propertyownership_changelist"))


@method_decorator(staff_member_required, name="dispatch")
class ImportPropertiesView(ImportTripWixMixin, generic.FormView):
    template_name = "admin/import_properties.html"
    form_class = ImportFileForm

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        owners_file = request.FILES.get("owners")

        if not owners_file.name.endswith(".json"):
            return HttpResponseBadRequest("Only .json file is accepted for properties upload")

        properties = json.load(owners_file)
        import_object = ImportPropertiesTripWix(properties=properties)
        import_object.run(import_photos=False)
        return redirect(reverse_lazy("admin:properties_property_changelist"))


@method_decorator(staff_member_required, name="dispatch")
class ImportAmenitiesView(ImportTripWixMixin, generic.FormView):
    template_name = "admin/import_properties.html"
    form_class = ImportFileForm

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        owners_file = request.FILES.get("owners")

        if not owners_file.name.endswith(".json"):
            return HttpResponseBadRequest("Only .json file is accepted for properties upload")

        amenities = json.load(owners_file)
        import_object = ImportAmenities(amenities)
        import_object.run()
        return redirect(reverse_lazy("admin:properties_property_changelist"))


@method_decorator(staff_member_required, name="dispatch")
class ImportRatesView(ImportTripWixMixin, generic.FormView):
    template_name = "admin/import_properties.html"
    form_class = ImportFileForm

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        owners_file = request.FILES.get("owners")

        if not owners_file.name.endswith(".json"):
            return HttpResponseBadRequest("Only .json file is accepted for properties upload")

        rates = json.load(owners_file)
        import_object = ImportRates(rates)
        import_object.run()
        return redirect(reverse_lazy("admin:properties_property_changelist"))


def update_property_active_amenities(request):
    from .models import PropertyAmenity

    try:
        data = json.loads(request.body)
        property_id = data.get("property_id")
        active_amenities = data.get("active_amenities")

        PropertyAmenity.objects.filter(property_id=property_id).delete()
        PropertyAmenity.objects.bulk_create(
            [PropertyAmenity(property_id=property_id, amenity_id=amenity_id) for amenity_id in active_amenities]
        )
        return JsonResponse({"status": "success"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)})


def get_property_active_amenities(request, property_id):
    from .models import PropertyAmenity

    active_amenities = PropertyAmenity.objects.filter(property_id=property_id).values_list("amenity_id", flat=True)
    return JsonResponse({"active_amenities": list(active_amenities)})



