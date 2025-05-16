import pytest

from apps.properties.models import PropertyBedroomsConfigType
from apps.tools.tests import AdminTestMixin

from ..factories import PropertyBedroomsConfigTypeFactory


@pytest.mark.django_db
class TestPropertyBedroomsConfigTypeAdmin(AdminTestMixin):
    def setup_method(self):
        self.factory = PropertyBedroomsConfigTypeFactory
        self.url = "/admin/properties/propertybedroomsconfigtype/"
        self.data = {
            "name": "Bedroom Config Type",
            "slug": "bedroom-config-type",
            "item_o": 0,
        }
        self.model = PropertyBedroomsConfigType
