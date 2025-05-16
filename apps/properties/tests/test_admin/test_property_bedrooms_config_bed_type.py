import pytest

from apps.properties.models import PropertyBedroomsConfigBedType
from apps.tools.tests import AdminTestMixin

from ..factories import PropertyBedroomsConfigBedTypeFactory


@pytest.mark.django_db
class TestPropertyBedroomsConfigBedTypeAdmin(AdminTestMixin):
    def setup_method(self):
        self.factory = PropertyBedroomsConfigBedTypeFactory
        self.url = "/admin/properties/propertybedroomsconfigbedtype/"
        self.data = {
            "name": "Bedroom Config Bed Type",
            "slug": "bedroom-config-bed-type",
            "item_o": 0,
        }
        self.model = PropertyBedroomsConfigBedType
