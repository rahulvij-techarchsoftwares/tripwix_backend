import pytest
from django.utils import timezone

from apps.properties.tests.factories import PropertyFactory

from ..models import Location
from .factories import LocationFactory


@pytest.mark.django_db
class TestLocation:
    def test_with_no_properties_published(self):
        LocationFactory()

        assert Location.objects.with_properties_published().count() == 0

    def test_with_properties_published(self):
        location = LocationFactory()
        publication_date = timezone.now() - timezone.timedelta(days=1)
        PropertyFactory(location=location, publication_date=publication_date, is_active=True)

        assert Location.objects.with_properties_published().count() == 1
