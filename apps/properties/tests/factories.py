import factory

from ..models import (
    Detail,
    DetailCategory,
    DetailCategorySection,
    Property,
    PropertyBedroomsConfigBedType,
    PropertyBedroomsConfigType,
    PropertyGroup,
    PropertyOwnership,
    PropertyType,
    PropertyTypology,
)


class PropertyTypeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PropertyType

    name = factory.Faker("name")
    slug = factory.Faker("slug")
    item_o = 0


class PropertyGroupFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PropertyGroup

    name = factory.Faker("name")
    sale_type = "r"
    description = factory.Faker("text")
    slug = factory.Faker("slug")


class PropertyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Property

    uid = factory.Faker("uuid4")
    name = factory.Faker("company")
    property_group = factory.SubFactory(PropertyGroupFactory)
    reference = factory.Faker("slug")
    slug = factory.Faker("slug")


class PropertyOwnershipFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PropertyOwnership

    name = factory.Faker("name")
    slug = factory.Faker("slug")
    account_id = factory.Faker("random_number", digits=4)
    item_o = 0


class PropertyTypologyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PropertyTypology

    name = factory.Faker("name")
    slug = factory.Faker("slug")
    item_o = 0


class DetailFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Detail

    name = factory.Faker("name")
    slug = factory.Faker("slug")
    detail_type = "text"


class DetailCategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DetailCategory

    name = factory.Faker("name")
    slug = factory.Faker("slug")
    item_o = 0


class DetailCategorySectionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DetailCategorySection

    category = factory.SubFactory(DetailCategoryFactory)
    name = factory.Faker("name")
    slug = factory.Faker("slug")
    item_o = 0


class PropertyBedroomsConfigBedTypeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PropertyBedroomsConfigBedType

    name = factory.Faker("name")
    slug = factory.Faker("slug")
    item_o = 0


class PropertyBedroomsConfigTypeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PropertyBedroomsConfigType

    name = factory.Faker("name")
    slug = factory.Faker("slug")
    item_o = 0
