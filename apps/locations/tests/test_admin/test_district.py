import pytest

from apps.locations.models import District
from apps.tools.tests import AdminTestMixin

from ..factories import DistrictFactory


@pytest.mark.django_db
class TestDistrictAdmin(AdminTestMixin):
    def setup_method(self):
        self.factory = DistrictFactory
        self.url = "/admin/locations/district/"
        self.data = {
            "name": "District",
            "slug": "district",
        }
        self.model = District
