import pytest

from apps.locations.models import City
from apps.tools.tests import AdminTestMixin

from ..factories import CityFactory


@pytest.mark.django_db
class TestCityAdmin(AdminTestMixin):
    def setup_method(self):
        self.factory = CityFactory
        self.url = "/admin/locations/city/"
        self.data = {
            "name": "City",
            "slug": "city",
        }
        self.model = City
