import pytest

from apps.properties.models import DetailCategorySection
from apps.tools.tests import AdminTestMixin

from ..factories import DetailCategoryFactory, DetailCategorySectionFactory


@pytest.mark.django_db
class TestDetailCategorySectionAdmin(AdminTestMixin):
    def setup_method(self):
        detail_category = DetailCategoryFactory()
        self.factory = DetailCategorySectionFactory
        self.url = "/admin/properties/detailcategorysection/"
        self.data = {
            "category": detail_category.pk,
            "name": "Owner",
            "slug": "owner",
        }
        self.model = DetailCategorySection
