from datetime import datetime
from decimal import Decimal

from django.contrib.gis.geos import Point
from django.db import transaction
from django.utils.text import slugify

from apps.locations.models import City, Country, Location, SubLocation
from apps.utils import strtobool

from .choices import (
    DETAIL_TYPE_BOOL,
    DETAIL_TYPE_DESCRIPTION,
    DETAIL_TYPE_OPTION,
    DETAIL_TYPE_OPTIONS,
    DETAIL_TYPE_TEXT,
    DETAIL_TYPE_TIME,
)
from .models import (
    Detail,
    DetailOption,
    Property,
    PropertyDetailValues,
    PropertyGroup,
    PropertyGroupDetails,
    PropertyManager,
    PropertyOwnership,
    PropertyType,
    PropertyTypology,
)
from .tasks import fetch_images_from_google_drive


class ImportPropertiesTripWix(object):
    properties_list = list()

    def __init__(self, properties, *args, **kwargs):
        self.properties_list = properties

    def get_properties_list(self):
        return self.properties_list

    @property
    def property_group(self):
        return PropertyGroup.objects.first()

    @staticmethod
    def get_owner(owner_id):
        if not owner_id:
            return None

        return PropertyOwnership.objects.get(account_id=owner_id)

    @staticmethod
    def get_coordinates(coordinates):
        if not coordinates:
            return None
        split_coordinates = coordinates.replace(" ", "").replace(",", ",").split(",")
        points = [float(point) for point in split_coordinates]

        return Point(points[::-1])  # reverse the order of points (django limitation)

    @staticmethod
    def get_city(name):
        city, _ = City.objects.get_or_create(slug=slugify(name), defaults={"name": name, "slug": slugify(name)})

        return city

    @staticmethod
    def get_country(name):
        return Country.objects.get(name=name)

    def get_location(self, city, country, destination):
        city_obj = self.get_city(city)
        country_obj = self.get_country(country)

        location, _ = Location.objects.get_or_create(
            country=country_obj,
            slug=slugify(f"{destination} {country}"),
            defaults={
                "country": country_obj,
                "name": f"{destination}, {country}",
                "slug": slugify(f"{destination}, {country}"),
            },
        )

        return location

    def get_create_typology(self, property, prop_type_name):
        typology_name = prop_type_name[0] + str(property.get("noOfBedrooms", 0))
        try:
            return self.prop_typology_dict[typology_name]
        except KeyError:
            new_typology = PropertyTypology.objects.create(name=typology_name, slug=typology_name)
            self.prop_typology_dict[typology_name] = new_typology.id
            return new_typology.id

    def get_create_manager(self, property, manager_id):
        try:
            manager = self.prop_managers_dict[manager_id]
        except KeyError:
            name = property.get("propertyManager") or property.get("propmanfname")
            manager = PropertyManager.objects.create(id=manager_id, name=name)
            self.prop_managers_dict[manager_id] = manager.name
        return manager_id

    def get_content(self, value):
        value_list = value.split("\n")

        description = ""
        for val in value_list:
            description += f"<p>{val}</p>"

        return description

    def get_create_sublocation(self, sublocation, location):
        if not sublocation:
            return None

        location, _ = SubLocation.objects.get_or_create(
            slug=slugify(f"{sublocation} {location.name}"),
            defaults={
                "name": sublocation,
                "slug": slugify(f"{sublocation} {location.name}"),
                "location": location,
            },
        )

        return location

    def get_hostify_id(self, hostify_link):
        if hostify_link:
            try:
                return hostify_link.split("view/")[1]
            except IndexError:
                return None

    def save_properties(self):
        properties = self.get_properties_list()
        properties_data = list()

        for prop in properties:
            property_id = prop.get("propertyId", "")
            if property_id == "" or property_id == " ":
                continue

            print(f'SAVING PROPERTY - {prop.get("propertyId")}')
            name = prop.get("propertyName")
            location = self.get_location(
                prop.get("city", ""),
                prop.get("country", ""),
                prop.get("destinationgpis", ""),
            )
            hostify_id = self.get_hostify_id(prop.get("hostifyLink", ""))
            data = {
                "name": prop.get("propertyId"),
                "content": self.get_content(prop.get("descriptiveText")),
                "title": name,
                "reference": prop.get("propertyId"),
                "typology_id": (
                    self.get_create_typology(prop, prop.get("propertyType")) if prop.get("propertyType") else None
                ),
                "property_type_id": self.prop_type_dict.get(prop.get("propertyType")),
                "ownership": self.get_owner(prop.get("ownerid", "")),
                "point": self.get_coordinates(prop.get("gpsCoordinates", "")),
                "location": location,
                "sublocation": self.get_create_sublocation(prop.get("communitygpis", ""), location),
                "address": prop.get("streetNameAndNumber"),
                "seo_title": prop.get("seoTitle", ""),
                "seo_description": prop.get("metaDescription", ""),
                "commission": Decimal(str(prop.get("commission")).replace("%", "")),
                "slug": f'{prop.get("propertyId")}{slugify(name)}',
                "property_group": self.property_group,
                "manager_id": self.get_create_manager(prop, prop.get("propmanid")) if prop.get("propmanid") else None,
                "standard_photos_url": prop.get("standardPhotos"),
                "hostify_id": hostify_id,
            }

            properties_data.append(Property(**data))

        properties_objs = Property.objects.bulk_create(
            properties_data,
            update_conflicts=True,
            update_fields=[
                "name",
                "reference",
                "typology",
                "ownership",
                "point",
                "location",
                "sublocation",
                "seo_title",
                "seo_description",
                "commission",
                "property_group",
                "title",
                "property_type",
                "address",
                "slug",
                "manager",
                "standard_photos_url",
            ],
            unique_fields=["reference"],
        )
        return properties_objs

    @staticmethod
    def get_detail_option(detail, value):
        detail_option, _ = DetailOption.objects.get_or_create(
            detail=detail,
            slug=slugify(value),
            defaults={
                "detail": detail,
                "name": value,
                "slug": slugify(value),
            },
        )

        return detail_option

    def get_detail_options(self, detail, value):
        return DetailOption.objects.filter(detail=detail, name__in=value)

    @staticmethod
    def get_required_fields():
        """
        {'field_name': 'value'}
        """
        return {"propertySizeSqm": 0}

    def save_property_details(self, property_dict):
        detail_fields = Detail.objects.all().values_list("slug", flat=True)
        detail_values = list()
        detail_options = list()
        remarks = ""
        property_object = Property.objects.get(reference=property_dict.get("propertyId"))

        for field in detail_fields:
            print(f'SAVING DETAIL - {property_dict.get("propertyId")} - {field}')
            value = property_dict.get(field)
            required_fields = self.get_required_fields()
            if value is None:
                if field in list(required_fields.keys()):
                    value = required_fields.get(field)
                else:
                    continue

            detail = Detail.objects.get(slug=field)
            if field == "dateOfInspection":
                date_format = "%Y-%m-%d"
                try:
                    value = value.split("T")[0]
                    datetime.strptime(value, date_format)
                except AttributeError:
                    remarks += f"Detail Error {field}: {value}\n"
                    continue
            elif field in ["offerStartDate", "offerEndDate"]:
                date_format = "%d %b %Y"
                value = value.replace("\xa0", " ")
                try:
                    value = str(datetime.strptime(value, date_format).date())
                except AttributeError:
                    remarks += f"Detail Error {field}: {value}\n"
                    continue
            elif detail.detail_type == DETAIL_TYPE_OPTION:
                value = self.get_detail_option(detail, value)
            elif detail.detail_type == DETAIL_TYPE_OPTIONS:
                detail_options.append({"property_id": property_object.pk, field: value.split(",")})

            elif detail.detail_type == DETAIL_TYPE_BOOL:
                if type(value) != bool:
                    try:
                        value = strtobool(value)
                    except ValueError:
                        property_object.note += f"Detail Error {field}: {value}\n"
                        property_object.save()
                        continue
            elif detail.detail_type == DETAIL_TYPE_TIME:
                value = value.split("T")[1][:-1]
            elif detail.detail_type == DETAIL_TYPE_TEXT:
                value = value[:254]
            elif detail.detail_type == DETAIL_TYPE_DESCRIPTION:
                value_list = value.split("\n")

                description = ""
                for val in value_list:
                    description += f"<p>{val}</p>"

                value = description

            property_group_detail = PropertyGroupDetails.objects.get(detail=detail, property_group=self.property_group)
            detail_value = PropertyDetailValues(
                property_object=property_object,
                property_group_detail=property_group_detail,
            )

            try:
                detail_value.set_value(detail.detail_type, value)
            except:
                remarks += f"Detail Error {field}: {value}\n"

            detail_values.append(detail_value)

        if remarks != "":
            property_object.note += remarks
            property_object.save()

        return detail_values, detail_options

    def save_details(self):
        properties = self.get_properties_list()
        detail_values = list()
        detail_options = list()
        ThroughDetailOption = PropertyDetailValues.detail_options.through
        for prop in properties:
            try:
                detail_value, detail_option = self.save_property_details(prop)
            except:
                continue
            detail_values += detail_value
            detail_options += detail_option  # list of dictionary of options

        PropertyDetailValues.objects.bulk_create(
            detail_values,
            update_conflicts=True,
            update_fields=[
                "detail_option",
                "text_value",
                "bool_value",
                "description_value",
                "number_value",
                "integer_value",
                "date_value",
                "time_value",
            ],
            unique_fields=[
                "property_object",
                "property_group_detail",
            ],
        )

        detail_option_list = list()
        detail_value_list = list()
        for option in detail_options:
            prop = Property.objects.get(pk=option.pop("property_id"))
            for key, value in option.items():
                detail_value = PropertyDetailValues.objects.get(
                    property_object=prop, property_group_detail__detail__slug=key
                )

                for val in value:
                    detail_option = DetailOption.objects.filter(
                        name=val, detail=detail_value.property_group_detail.detail
                    ).first()
                    if detail_option is None:
                        continue

                    detail_option_list.append(
                        ThroughDetailOption(
                            propertydetailvalues=detail_value,
                            detailoption=detail_option,
                        )
                    )
                detail_value_list.append(detail_value.pk)

        exclude_filter = dict()
        if len(detail_value_list) > 0:
            exclude_filter["propertydetailvalues_id__in"] = detail_value_list

        ThroughDetailOption.objects.filter(**exclude_filter).delete()
        ThroughDetailOption.objects.bulk_create(detail_option_list)

    def save_images(self):
        proprety_ids = [prop.get("propertyId") for prop in self.get_properties_list()]
        properties = Property.objects.filter(reference__in=proprety_ids)
        for prop in properties:
            fetch_images_from_google_drive.delay(prop.pk)

    def run(self, import_photos=False):
        self.prop_type_dict = dict(PropertyType.objects.values_list("name", "id"))
        self.prop_typology_dict = dict(PropertyTypology.objects.values_list("name", "id"))
        self.prop_managers_dict = dict(PropertyManager.objects.values_list("id", "name"))

        with transaction.atomic():
            self.save_properties()
            self.save_details()

        if import_photos is True:
            self.save_images()

        return True
