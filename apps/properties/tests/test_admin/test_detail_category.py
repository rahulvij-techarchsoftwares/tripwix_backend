import pytest

from apps.properties.models import DetailCategory
from apps.tools.tests import AdminTestMixin

from ..factories import DetailCategoryFactory


@pytest.mark.django_db
class TestDetailCategoryAdmin(AdminTestMixin):
    def setup_method(self):
        self.factory = DetailCategoryFactory
        self.url = "/admin/properties/detailcategory/"
        self.data = {
            "name": "Owner",
            "slug": "owner",
            "item_o": 0,
        }
        self.model = DetailCategory
