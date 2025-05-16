import pytest
from faker import Faker

from apps.locations.models import Country
from apps.tools.tests import AdminTestMixin

from ..factories import CountryFactory

faker = Faker()


@pytest.mark.django_db
class TestCountryAdmin(AdminTestMixin):
    def setup_method(self):
        self.factory = CountryFactory
        self.url = "/admin/locations/country/"
        self.data = {
            "name": "Country",
            "phone": str(faker.random_number(digits=3)),
            "alpha3": faker.country_code("alpha-3"),
            "numcode": faker.random_number(digits=3),
        }
        self.model = Country

    def test_list(self, admin_client):
        self.factory()
        response = admin_client.get(self.url)

        assert response.context_data["cl"].result_list.count() == 1

    def test_post(self, admin_client):
        url = f"{self.url}add/"
        self.data.update({"alpha2": faker.country_code()})
        response = admin_client.post(url, data=self.data)

        assert response.status_code == 302
        assert self.model.objects.count() == 1

    def test_update(self, admin_client):
        obj = self.factory()
        self.data.update({"alpha2": obj.pk})
        url = f"{self.url}{obj.pk}/change/"
        response = admin_client.post(url, data=self.data)

        assert response.status_code == 302
        assert self.model.objects.count() == 1

        obj.refresh_from_db()
        for key, value in self.data.items():
            assert getattr(obj, key) == value
