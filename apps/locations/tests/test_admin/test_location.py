import pytest

from apps.locations.models import Location
from apps.tools.tests import AdminTestMixin

from ..factories import LocationFactory


@pytest.mark.django_db
class TestLocationAdmin(AdminTestMixin):
    def setup_method(self):
        self.factory = LocationFactory
        self.url = "/admin/locations/location/"
        self.data = {
            "name": "Location",
            "slug": "location",
        }
        self.model = Location

    def test_order_save(self, admin_client):
        obj = self.factory()
        response = admin_client.get(self.url)
        locations = response.context_data["cl"].result_list.count()

        response = admin_client.post(
            self.url,
            data={
                f"form-0-sort_order": 3,
                f"form-0-id": obj.pk,
                "_save": "Save",
                "select_across": "0",
                "form-TOTAL_FORMS": locations,
                "form-INITIAL_FORMS": locations,
                "form-MIN_NUM_FORMS": 0,
                "form-MAX_NUM_FORMS": 1000,
            },
        )

        assert response.status_code == 302
        obj.refresh_from_db()
        assert obj.sort_order == 3
