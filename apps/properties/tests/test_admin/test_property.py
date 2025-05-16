import uuid

import pytest
from faker import Faker

from apps.properties.models import Property, PropertyBedroomsConfig
from apps.tools.tests import AdminTestMixin

from ..factories import (
    PropertyBedroomsConfigBedTypeFactory,
    PropertyBedroomsConfigTypeFactory,
    PropertyFactory,
    PropertyGroupFactory,
)

faker = Faker()


@pytest.mark.django_db
class TestPropertyAdmin(AdminTestMixin):
    def setup_method(self):
        self.factory = PropertyFactory
        self.url = "/admin/properties/property/"
        self.data = {
            "name": "Property",
            "reference": faker.word(),
        }
        self.model = Property

    def test_list(self, admin_client):
        property_group = PropertyGroupFactory()
        self.factory(property_group=property_group)
        self.factory(property_group=property_group)
        response = admin_client.get(self.url)

        assert response.status_code == 200
        assert response.context_data["cl"].result_list.count() == 2

    def test_post(self, admin_client):
        property_group = PropertyGroupFactory()

        url = f"{self.url}add/"
        self.data.update({"property_group": property_group.pk, "uid": str(uuid.uuid4())})
        response = admin_client.post(url, data=self.data)

        assert response.status_code == getattr(self, "post_status_code", 302)
        assert self.model.objects.count() == 1

    def test_media(self, admin_client):
        obj = self.factory()
        url = f"{self.url}{obj.pk}/media/"
        standard_photos_url = faker.url()
        data = {
            "standard_photos_url": standard_photos_url,
        }
        response = admin_client.post(url, data=data)

        assert response.status_code == 302
        obj.refresh_from_db()
        assert obj.standard_photos_url == standard_photos_url

    def test_location(self, admin_client):
        obj = self.factory()
        url = f"{self.url}{obj.pk}/location/"
        address = faker.address()
        data = {
            "address": address,
        }
        response = admin_client.post(url, data=data)

        assert response.status_code == 302
        obj.refresh_from_db()
        assert obj.address == address

    def test_construction(self, admin_client):
        bedroom_type = PropertyBedroomsConfigTypeFactory()
        bed_type = PropertyBedroomsConfigBedTypeFactory()
        obj = self.factory()
        url = f"{self.url}{obj.pk}/construction/"
        data = {
            "bedrooms_configurations-TOTAL_FORMS": 1,
            "bedrooms_configurations-INITIAL_FORMS": 0,
            "bedrooms_configurations-MIN_NUM_FORMS": 0,
            "bedrooms_configurations-MAX_NUM_FORMS": 1000,
            "bedrooms_configurations-0-id": "",
            "bedrooms_configurations-0-property_object": obj.pk,
            "bedrooms_configurations-0-bedroom_type": bedroom_type.pk,
            "bedrooms_configurations-0-number": 1,
            "bedrooms_configurations-0-bed_type": bed_type.pk,
            "bedrooms_configurations-0-description": "Description",
            "bedrooms_configurations-__prefix__-id": "",
            "bedrooms_configurations-__prefix__-property_object": obj.pk,
            "bedrooms_configurations-__prefix__-bedroom_type": "",
            "bedrooms_configurations-__prefix__-number": 1,
            "bedrooms_configurations-__prefix__-bed_type": "",
            "bedrooms_configurations-__prefix__-description": "Description",
        }
        response = admin_client.post(url, data=data)

        assert response.status_code == 302
        assert PropertyBedroomsConfig.objects.count() == 1

    def test_related(self, admin_client):
        property_group = PropertyGroupFactory()
        obj = self.factory(property_group=property_group)
        url = f"{self.url}{obj.pk}/related/"
        related = PropertyFactory(property_group=property_group)
        data = {
            "related": related.pk,
        }
        response = admin_client.post(url, data=data)

        assert response.status_code == 302
        obj.refresh_from_db()
        assert obj.related.count() == 1
        assert obj.related.first() == related
