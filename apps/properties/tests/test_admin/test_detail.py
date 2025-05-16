import pytest

from apps.properties.models import Detail
from apps.tools.tests import AdminTestMixin

from ..factories import DetailFactory


@pytest.mark.django_db
class TestDetailAdmin(AdminTestMixin):
    def setup_method(self):
        self.factory = DetailFactory
        self.url = "/admin/properties/detail/"
        self.data = {
            "name": "Owner",
            "slug": "owner",
            "detail_type": "text",
            "unit": "text",
            "options-TOTAL_FORMS": 3,
            "options-INITIAL_FORMS": 0,
            "options-MIN_NUM_FORMS": 0,
            "options-MAX_NUM_FORMS": 1000,
        }
        self.model = Detail

    def test_update(self, admin_client):
        obj = self.factory()
        url = f"{self.url}{obj.pk}/change/"
        response = admin_client.post(url, data=self.data)

        assert response.status_code == getattr(self, "update_status_code", 302)
        assert self.model.objects.count() == 1

        obj.refresh_from_db()
        self.data.pop("options-TOTAL_FORMS")
        self.data.pop("options-INITIAL_FORMS")
        self.data.pop("options-MIN_NUM_FORMS")
        self.data.pop("options-MAX_NUM_FORMS")
        for key, value in self.data.items():
            assert getattr(obj, key) == value
