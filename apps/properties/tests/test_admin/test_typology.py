import pytest

from apps.properties.models import PropertyTypology
from apps.tools.tests import AdminTestMixin

from ..factories import PropertyTypologyFactory


@pytest.mark.django_db
class TestPropertyTypologyAdmin(AdminTestMixin):
    def setup_method(self):
        self.factory = PropertyTypologyFactory
        self.url = "/admin/properties/propertytypology/"
        self.data = {
            "name": "Owner",
            "slug": "owner",
            "item_o": 0,
        }
        self.model = PropertyTypology
