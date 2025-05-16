import pytest

from apps.locations.models import Region
from apps.tools.tests import AdminTestMixin

from ..factories import RegionFactory


@pytest.mark.django_db
class TestRegionAdmin(AdminTestMixin):
    def setup_method(self):
        self.factory = RegionFactory
        self.url = "/admin/locations/region/"
        self.data = {
            "name": "Region",
            "slug": "region",
        }
        self.model = Region
