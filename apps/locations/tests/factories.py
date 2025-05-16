import factory
from faker import Faker

from apps.locations.models import City, Country, District, Location, Region

faker = Faker()


class LocationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Location

    name = factory.Faker("city")
    slug = factory.Faker("slug")


class CityFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = City

    name = factory.Faker("city")
    slug = factory.Faker("slug")


class DistrictFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = District

    name = factory.Faker("city")
    slug = factory.Faker("slug")


class RegionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Region

    name = factory.Faker("city")
    slug = factory.Faker("slug")


class CountryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Country

    alpha2 = factory.Faker("country_code")
    name = factory.Faker("country")
    phone = faker.phone_number()[1:4]
    alpha3 = faker.country_code("alpha-3")
    numcode = faker.random_number(digits=3)
