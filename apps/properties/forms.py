import json
import uuid

from django import forms
from django.conf import settings
from django.contrib.admin.widgets import AdminDateWidget, AdminTimeWidget
from django.contrib.gis.geos import GEOSGeometry
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_admin_kubi.widgets import TinyMceEditorWidget

from apps.core.widgets import SelectizeMultipleWidget
from apps.locations.models import City, Country

from . import choices
from .models import Ambassador, Property, PropertyDetailValues, PropertyGroup, Rate
from .widgets import (
    DecimalWithDropdownWidget,
    LocationWidget,
    MySelectizeMultipleWidget,
    MySelectizeWidget,
    PointWidget,
    PropertiesMany2ManyWidget,
    SelectizeWidget,
    VisibilityWidget,
)


class DecimalWithDropdownField(forms.MultiValueField):
    def __init__(self, *args, **kwargs):
        fee_choices = [('', 'Select a value type')] + list(choices.FEE_TYPE_CHOICES)

        fields = [
            forms.FloatField(min_value=0),
            forms.ChoiceField(choices=fee_choices),
        ]

        widgets = [
            forms.NumberInput(attrs={"class": "form-control"}),
            forms.Select(
                attrs={"class": "form-control"},
                choices=fee_choices,
            ),
        ]

        super().__init__(fields, widget=DecimalWithDropdownWidget(widgets=widgets), *args, **kwargs)

    def compress(self, data_list):
        if data_list:
            return json.dumps(
                {
                    "value": str(data_list[0]),
                    "value_type": str(data_list[1]),
                }
            )
        return json.dumps(
            {
                "value": None,
                "value_type": None,
            }
        )


class CountryVatRateChoiceField(forms.ChoiceField):
    def __init__(self, vat_choices: list = list(), *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.choices = [("", "Select a VAT Rate")] + vat_choices


class PropertyChangeForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.fields["name"].label = 'Property number'
            self.fields["reference"].label = 'Code'
        except KeyError:
            pass
        slug_bases_url = self.instance
        if self.instance.pk and self.instance.property_group:
            slug_bases_url = self.instance.property_group
        # self.fields['slug'].widget = SlugWidget(
        #     url=slug_bases_url,
        #     attrs={'class': 'mt mt-field-page_url-%s'}
        # )

        # TODO: Auto generate reference
        # if conf.PROPERTY_CONFIGURATION['AUTO_GENERATE_REFERENCE'] and not self.instance.pk:
        #     self.fields['reference'].initial = get_generate_reference()

    def clean(self):
        slug = self.cleaned_data.get("slug", self.cleaned_data.get("slug_%s" % settings.LANGUAGE_CODE, None))

        if not slug:
            # Generate Unique Slug
            slug = uuid.uuid4().hex

        if self.cleaned_data.get("is_active", False):
            self.cleaned_data["publication_date"] = self.cleaned_data.get("publication_date", timezone.now())

        # TODO: Auto generate reference
        # if conf.PROPERTY_CONFIGURATION['AUTO_GENERATE_REFERENCE'] and not self.instance.pk:
        #     self.cleaned_data["reference"] = get_generate_reference()

        return super(PropertyChangeForm, self).clean()

    class Meta:
        model = Property
        fields = "__all__"
        exclude = ["property_group"]
        widgets = {
            "property_type": SelectizeWidget,
            "typology": SelectizeWidget,
            "ownership": SelectizeWidget,
            "commission_type": SelectizeWidget,
            "is_active": VisibilityWidget,
        }


class PropertyAmenitiesForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = ("amenities",)
        widgets = {"amenities": MySelectizeMultipleWidget}


class PropertyLocationForm(forms.ModelForm):
    country = forms.ModelChoiceField(queryset=Country.objects.all(), required=False)
    city = forms.ModelChoiceField(queryset=City.objects.all(), required=False)
    gps_coordinates_manual = forms.CharField(
        required=False,
        label="GPS Coordinates",
        help_text="Use this field to manually set GPS coordinates. Format: 'latitude,longitude' (e.g. '37.7749295,-122.4194155')",
    )

    def __init__(self, *args, **kwargs):
        super(PropertyLocationForm, self).__init__(*args, **kwargs)
        if self.instance:
            if self.instance.point:
                self.fields['gps_coordinates_manual'].initial = f'{self.instance.point.y},{self.instance.point.x}'
            if self.instance.location:
                self.fields['country'].initial = self.instance.location.country
                self.fields['city'].initial = self.instance.location.cities.first()

    class Meta:
        model = Property
        fields = ("location", "address", "gps_coordinates_manual", "point", "sublocation")

        widgets = {
            "location": LocationWidget(),
            "point": PointWidget(),
        }

    class Media:
        js = (
            'admin/js/jquery.min.js',
            'admin/js/locationOptions.js',
        )

    def clean_gps_coordinates_manual(self):
        data = self.cleaned_data['gps_coordinates_manual']
        if data:

            def normalize_coordinate(coord):
                return float(coord.replace(",", "").replace(" ", ""))

            try:
                lat, lng = data.split(",")
            except ValueError:
                try:
                    lat, lng = data.split()
                except ValueError:
                    raise ValidationError("Invalid Coordinates format")
            try:
                return GEOSGeometry(f"POINT({normalize_coordinate(lng)} {normalize_coordinate(lat)})")
            except ValueError:
                raise ValidationError("Invalid Coordinates format")
        return data

    def clean(self):
        cleaned_data = super().clean()
        cleaned_data.pop("country", None)
        if self.instance:
            changed_fields = self.changed_data
            if "gps_coordinates_manual" in changed_fields:
                cleaned_data['point'] = self.cleaned_data["gps_coordinates_manual"]
        else:
            if not cleaned_data.get("point"):
                cleaned_data['point'] = self.cleaned_data["gps_coordinates_manual"]
        return cleaned_data


def get_text_field_attrs_by_unit(unit):
    data_attrs = dict()
    if unit:
        limits = unit.split(",")
        data_attrs = {"data-limit_words": limits[0], "data-limit_chars": limits[1]}
    return data_attrs


def form_special_attribute(detail):
    return "detail_%s" % detail.slug.replace("-", "_")


def get_slug_field(detail_field):
    return detail_field[7:].replace("_", "-")


class PropertyDetailsForm(forms.ModelForm):
    tagline = forms.CharField(
        label=_("Tagline"), max_length=255, required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )
    ambassador = forms.ModelChoiceField(
        queryset=Ambassador.objects.all(), label=_("Ambassador"), required=False, widget=MySelectizeWidget()
    )

    def __init__(self, category=None, enable_change_vat_input=False, **kwargs):
        super(PropertyDetailsForm, self).__init__(**kwargs)
        if self.instance:
            self.fields['tagline'].initial = self.instance.tagline
            self.fields['ambassador'].initial = self.instance.ambassador
        out_fields = dict()
        details_fields = (
            self.instance.property_group.details_queryset().select_related("detail").filter(section__category=category)
        )
        self.detail_ids = details_fields.values_list("detail__slug", flat=True)
        number_with_value_type_selector_initial_values = {}

        for group_detail in details_fields:
            # Set field vars
            field_label = "%s" % group_detail.detail.name
            is_required = group_detail.is_required
            help_text = group_detail.detail.help_text if group_detail.detail.help_text else ""
            detail_type = group_detail.detail.detail_type

            if detail_type == choices.DETAIL_TYPE_TEXT:
                field = forms.CharField()
                initial_value = group_detail.detail.initial_text_value
                if initial_value:
                    field.initial = initial_value
            elif detail_type == choices.DETAIL_TYPE_COLOR:
                field = forms.CharField()
            elif detail_type == choices.DETAIL_TYPE_BOOL:
                field = forms.BooleanField()
                is_required = False

            elif detail_type == choices.DETAIL_TYPE_NUMBER_WITH_VALUE_TYPE_SELECTOR:
                try:
                    initial_choice = group_detail.detail.initial_number_with_value_type_selector_value
                    number_with_value_type_selector_initial_values[form_special_attribute(group_detail.detail)] = (
                        '',
                        initial_choice,
                    )
                except AttributeError:
                    pass
                field = DecimalWithDropdownField()
                is_required = False

            elif detail_type == choices.DETAIL_TYPE_OPTION:
                field = forms.ModelChoiceField(queryset=group_detail.detail.options, widget=MySelectizeWidget)

            elif detail_type == choices.DETAIL_TYPE_COUNTRY_VAT_CHOICES:
                try:
                    property_country_vat_rates = self.instance.location.country.vat_rates.all()
                    vat_choices = [(rate.rate, f'{rate.name} - {rate.rate}%') for rate in property_country_vat_rates]
                except AttributeError:
                    vat_choices = list()
                field = CountryVatRateChoiceField(
                    vat_choices=vat_choices, disabled=not enable_change_vat_input or not len(vat_choices)
                )

            elif detail_type == choices.DETAIL_TYPE_OPTIONS:
                field = forms.ModelMultipleChoiceField(
                    queryset=group_detail.detail.options,
                    widget=SelectizeMultipleWidget,
                )

            elif detail_type == choices.DETAIL_TYPE_DATE:
                field = forms.DateField(widget=AdminDateWidget(attrs={"placeholder": "DD/MM/YYYY"}))

            elif detail_type == choices.DETAIL_TYPE_TIME:
                field = forms.TimeField(widget=AdminTimeWidget(attrs={"placeholder": "HH:MM"}))
            elif detail_type == choices.DETAIL_TYPE_NUMBER:
                field = forms.DecimalField()

            elif detail_type == choices.DETAIL_TYPE_INTEGER:
                field = forms.IntegerField()

            elif detail_type == choices.DETAIL_TYPE_INTEGER_SUM:
                field = forms.CharField()

            elif detail_type == choices.DETAIL_TYPE_DESCRIPTION:
                attrs = {"class": "vLargeTextField", "rows": 4, "cols": 40}
                attrs.update(get_text_field_attrs_by_unit(group_detail.detail.unit))
                field = forms.CharField(widget=TinyMceEditorWidget(attrs=attrs))
                initial_value = group_detail.detail.initial_description_value
                if initial_value:
                    field.initial = initial_value
            else:
                field = forms.CharField()

            if field:
                field.label = field_label
                field.help_text = help_text
                field.required = is_required
                out_fields[form_special_attribute(group_detail.detail)] = field

        self.fields.update(out_fields)

        # DEFINE INITIAL DETAIL DATA FROM DETAILS
        self.detail_value_slug = list()
        if self.instance and self.instance.pk:
            for item in self.instance.detail_values.all():
                field_name = form_special_attribute(item.property_group_detail.detail)
                self.initial[field_name] = item.value
                number_with_value_type_selector_initial_values.pop(field_name, None)
            self.detail_value_slug = self.instance.details.values_list("detail__slug", flat=True)
            for key, value in number_with_value_type_selector_initial_values.items():
                self.initial[key] = value

    def save(self, *args, **kwargs):
        obj = super().save(*args, **kwargs)
        for key, item in self.cleaned_data.items():
            if key == "related":
                self.instance.related.set(item)
                self.instance.save()
                continue
            elif key == "tagline":
                self.instance.tagline = item
                self.instance.save()
                continue
            elif key == "ambassador":
                self.instance.ambassador = item
                self.instance.save()
                continue
            elif key == "photos":
                self.instance.photos.set(item)
                self.instance.save()
                image = self.instance.photos.first()
                continue
            elif key == "standard_photos_url":
                self.instance.standard_photos_url = item
                self.instance.save()
                continue
            else:
                if key:
                    slug = get_slug_field(key)
            detail = self.instance.property_group.propertygroupdetails_set.get(detail__slug=slug)
            property_detail, _ = PropertyDetailValues.objects.update_or_create(
                property_object=self.instance,
                property_group_detail=detail,
                defaults={
                    "property_object": self.instance,
                    "property_group_detail": detail,
                },
            )
            property_detail.add_value(item)
        return obj

    class Meta:
        model = Property
        fields = (
            'tagline',
            'ambassador',
        )
        widgets = {"property_group": forms.widgets.Select(attrs={"readonly": True, "disabled": True})}


class PropertyGroupForm(forms.ModelForm):
    class Meta:
        model = PropertyGroup
        fields = ()


class PropertyRelatedForm(PropertyDetailsForm):
    class Meta:
        model = Property
        fields = ("related",)  # 'related_reviews'

        widgets = {
            "related": PropertiesMany2ManyWidget(
                verbose_name="Related to",
                layout="table",
            ),  # PropertySelectMultipleWidget(),
        }


class PropertyMediaForm(PropertyDetailsForm):
    class Meta:
        model = Property
        fields = (
            "photos",
            "standard_photos_url",
        )

    def __init__(self, *args, **kwargs):
        disabled = kwargs.pop('disabled', False)
        super().__init__(*args, **kwargs)

        if disabled:
            self.fields['photos'].readonly = True
            for field_name in self.fields:
                self.fields[field_name].disabled = True
                self.fields[field_name].widget.attrs['readonly'] = True

    def clean(self):
        cleaned_data = super().clean()
        photos = cleaned_data.get("photos")
        for index, photo in enumerate(photos):
            if photo.order == index:
                continue
            photo.order = index
            photo.save()
        return cleaned_data


class RateForm(forms.ModelForm):
    class Meta:
        model = Rate
        fields = ['from_date', 'to_date', 'season', 'minimum_nights', 'website_sales_value']
        widgets = {
            'from_date': AdminDateWidget(attrs={'placeholder': 'DD/MM/YYYY'}),
            'to_date': AdminDateWidget(attrs={'placeholder': 'DD/MM/YYYY'}),
        }

    def __init__(self, *args, **kwargs):
        self.disabled = kwargs.pop('disabled', False)
        self.property = kwargs.pop('property', None)

        super().__init__(*args, **kwargs)
        if self.property:
            self.instance.property = self.property
        if self.disabled:
            for field in self.fields.values():
                field.widget.attrs['disabled'] = True
                field.disabled = True

    def clean(self):
        cleaned_data = super().clean()
        from_date = cleaned_data.get('from_date')
        to_date = cleaned_data.get('to_date')
        minimum_nights = cleaned_data.get('minimum_nights')
        website_sales_value = cleaned_data.get('website_sales_value')

        if not self.instance.property and self.property:
            self.instance.property = self.property

        if from_date and to_date:
            if from_date > to_date:
                self.add_error('from_date', 'Start date must be before end date.')

            overlapping_rates = Rate.objects.filter(
                property=self.instance.property,
                to_date__gte=from_date,
                from_date__lte=to_date,
            ).exclude(pk=self.instance.pk)

            if overlapping_rates.exists():
                self.add_error('from_date', 'The date range overlaps with an existing rate.')

            previous_rate = self.instance.get_previous_rate()
            if previous_rate and from_date <= previous_rate.to_date:
                self.add_error('from_date', 'Start date must be after the previous rate\'s end date.')

        if minimum_nights is not None and minimum_nights < 1:
            self.add_error('minimum_nights', 'Minimum nights must be at least 1.')

        if website_sales_value is not None and website_sales_value <= 0:
            self.add_error('website_sales_value', 'Rate value must be greater than 0.')

        return cleaned_data


class ImportFileForm(forms.Form):
    owners = forms.FileField()
