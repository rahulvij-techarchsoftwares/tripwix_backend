import pytest

from apps.properties.models import PropertyGroup, PropertyGroupDetails
from apps.tools.tests import AdminTestMixin

from ..factories import DetailCategorySectionFactory, DetailFactory, PropertyGroupFactory


@pytest.mark.django_db
class TestPropertyGroupAdmin(AdminTestMixin):
    def setup_method(self):
        self.factory = PropertyGroupFactory
        self.url = "/admin/properties/propertygroup/"
        self.data = {
            "name": "Property Group",
            "slug": "name",
            "sale_type": "r",
            "description": "Property Group Description",
            "sort_order_be": "ne",
            "sort_order_fe": "ne",
        }
        self.model = PropertyGroup

    def test_list(self, admin_client):
        self.factory()
        response = admin_client.get(self.url)

        assert response.context_data["cl"].result_list.count() == 1

    def test_detail(self, admin_client):
        detail = DetailFactory()
        section = DetailCategorySectionFactory()
        obj = self.factory()
        url = f"{self.url}{obj.pk}/details/"
        data = {
            "propertygroupdetails_set-TOTAL_FORMS": 1,
            "propertygroupdetails_set-INITIAL_FORMS": 0,
            "propertygroupdetails_set-MIN_NUM_FORMS": 0,
            "propertygroupdetails_set-MAX_NUM_FORMS": 1000,
            "propertygroupdetails_set-0-id": "",
            "propertygroupdetails_set-0-property_group": obj.pk,
            "propertygroupdetails_set-0-detail": detail.pk,
            "propertygroupdetails_set-0-section": section.pk,
            "propertygroupdetails_set-0-is_required": "on",
            "propertygroupdetails_set-0-sort_order": 0,
            "propertygroupdetails_set-__prefix__-id": "",
            "propertygroupdetails_set-__prefix__-property_group": obj.pk,
            "propertygroupdetails_set-__prefix__-detail": "",
            "propertygroupdetails_set-__prefix__-section": "",
            "propertygroupdetails_set-__prefix__-is_required": "on",
            "propertygroupdetails_set-__prefix__-sort_order": 0,
        }
        response = admin_client.post(url, data=data)

        assert response.status_code == 302
        assert PropertyGroupDetails.objects.count() == 1
