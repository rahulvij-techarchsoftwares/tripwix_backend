import pytest

from apps.properties.models import PropertyOwnership
from apps.tools.tests import AdminTestMixin

from ..factories import PropertyOwnershipFactory


@pytest.mark.django_db
class TestPropertyOwnershipAdmin(AdminTestMixin):
    def setup_method(self):
        self.factory = PropertyOwnershipFactory
        self.url = "/admin/properties/propertyownership/"
        self.data = {
            "name": "Owner",
            "slug": "owner",
            "account_id": 1234,
            "item_o": 0,
        }
        self.model = PropertyOwnership
