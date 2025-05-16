import pytest

from apps.properties.models import PropertyType
from apps.tools.tests import AdminTestMixin

from ..factories import PropertyTypeFactory


@pytest.mark.django_db
class TestPropertyTypeAdmin(AdminTestMixin):
    def setup_method(self):
        self.factory = PropertyTypeFactory
        self.url = "/admin/properties/propertytype/"
        self.data = {
            "name": "Owner",
            "slug": "owner",
            "item_o": 0,
        }
        self.model = PropertyType
