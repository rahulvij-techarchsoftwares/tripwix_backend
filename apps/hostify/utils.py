import json
import logging
import pprint
from datetime import date, time, timedelta
from decimal import Decimal

import requests
from bs4 import BeautifulSoup as bs
from django.db import transaction
from django.utils import timezone

from apps.core.services import RedisContextManager
from apps.external_apis.hostify.sdk import HostifyAPI
from apps.hostify.constants import (
    AVAILABLE_CALENDAR_RESERVATION_STATUS_MAPPING,
    VALID_PROPERTY_TYPES,
    CalendarStatusChoices,
)
from apps.hostify.models import PropertyCalendar
from apps.properties.models import DetailOption, Property, PropertyTax
import html
from html.parser import HTMLParser
import re


logger = logging.getLogger(__name__)


def get_location_details(latitude, longitude):
    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={latitude}&lon={longitude}"
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; MyScript/1.0; +https://meusite.com/bot)'}
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()

        address = data.get('display_name', 'Address not found')
        components = data.get('address', {})

        city = components.get('city', '') or components.get('town', '') or components.get('village', '')
        country = components.get('country', '')
        state = components.get('state', '')
        street = components.get('road', '') or components.get('street', '')

        return address, city, country, state, street, latitude, longitude

    return None, None, None, None, None, None, None


def sync_photos(property_obj, photos, hostify_api):
    response = hostify_api.process_photos(property_obj.hostify_id, photos)
    if not response.get('success', False):
        raise Exception(f"Failed to sync photos for property {property_obj.name}: {response}")


def sync_rooms(property_obj, rooms, hostify_api):
    response = hostify_api.process_rooms(property_obj.hostify_id, rooms)
    if not response.get('success', False):
        raise Exception(f"Failed to sync rooms for property {property_obj.name}: {response}")


def sync_amenities(property_obj, amenities, hostify_api):
    response = hostify_api.process_amenities(property_obj.hostify_id, amenities)
    if not response.get('success', False):
        raise Exception(f"Failed to sync amenities for property {property_obj.name}: {response}")


def toggle_listing_status(property_obj, enable: bool, hostify_api: HostifyAPI):
    channel_listed = int(enable)
    response = hostify_api.list_unlist_property(property_obj.hostify_id, channel_listed)

    if not response.get('success', False):
        raise Exception(
            f"Failed to {'enable' if enable else 'disable'} listing for property {property_obj.name}: {response}"
        )


def create_property_with_hostify(property_obj, hostify_api, called_from_celery=False):
    from apps.properties.models import Property

    location = getattr(property_obj, 'point', None)
    if not location:
        raise Exception(f"Property {property_obj.id} - {property_obj.name} does not have a location")

    address, city, country, state, street, latitude, longitude = get_location_details(location.y, location.x)
    property_obj.photos.all().update(is_synched=False)
    update_data = {
        "name": property_obj.name or '',
        "property_type": "apartment",
        "listing_type": "entire home",
        "lat": latitude,
        "lng": longitude,
        "address": address,
        "city": city,
        "country": country,
        "street": street,
    }

    response = hostify_api.create_listing(update_data)
    if not response.get('success', False):
        raise Exception(f"Failed to create listing for property {property_obj.name}: {response}")

    Property.objects.filter(id=property_obj.id).update(hostify_id=response.get('listingId'))


def is_property_active(property_obj):
    return property_obj.is_active or (
        (property_obj.publication_date and property_obj.publication_date <= timezone.now())
        and (property_obj.publication_end_date and property_obj.publication_end_date >= timezone.now())
    )



class HTMLToFormattedText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.output = []
        self.inside_p = False
        self.p_content = []
        self.last_was_newline = False

    def _append_single_newline(self):
        if not self.last_was_newline:
            self.output.append('\n')
            self.last_was_newline = True

    def handle_starttag(self, tag, attrs):
        if tag in ['ul', 'ol']:
            self._append_single_newline()
        elif tag == 'li':
            self._append_single_newline()
            self.output.append('- ')  
            self.last_was_newline = False
        elif tag == 'p':
            self.inside_p = True
            self.p_content = []

    def handle_endtag(self, tag):
        if tag == 'p':
            joined_p = ''.join(self.p_content).strip()
            if joined_p and joined_p != '\xa0':
                self.output.append(joined_p)
                self._append_single_newline()
            self.inside_p = False
            self.p_content = []

    def handle_data(self, data):
        text = html.unescape(data)
        text = text.replace('\r', '')
        
        if self.inside_p:
            self.p_content.append(text)
        else:
            if text.strip():
                self.output.append(text)
                self.last_was_newline = text.endswith('\n')

def html_to_formatted_text(html_content):
    if not html_content:
        return ""
    parser = HTMLToFormattedText()
    parser.feed(html_content)
    result = ''.join(parser.output).strip()
    result = re.sub(r'\n{2,}', '\n\n', result)
    return result


def format_space_data(property_obj):
    space = ""

    content = property_obj.content
    if content:
        space += f"{html_to_formatted_text(content)}\n"

    special_features = (
        property_obj.detail_values.filter(property_group_detail__detail__slug='specialFeatures').first() or ""
    )
    try:
        special_features = special_features.value
    except AttributeError:
        special_features = None
    if special_features:
        space += "\nSPECIAL FEATURES\n"
        space += f"{html_to_formatted_text(special_features)}\n"

    living_areas = property_obj.detail_values.filter(property_group_detail__detail__slug='livingAreas').first() or ""
    try:
        living_areas = living_areas.value
    except AttributeError:
        living_areas = None
    if living_areas:
        space += "\nLIVING AREAS\n"
        space += f"{html_to_formatted_text(living_areas)}\n"

    bed_and_bath = property_obj.detail_values.filter(property_group_detail__detail__slug='bedbath').first() or ""
    try:
        bed_and_bath = bed_and_bath.value
    except AttributeError:
        bed_and_bath = None
    if bed_and_bath:
        space += "\nBEDROOMS AND BATHROOMS\n"
        space += f"{html_to_formatted_text(bed_and_bath)}\n"

    location = property_obj.detail_values.filter(property_group_detail__detail__slug='location').first() or ""
    try:
        location = location.value
    except AttributeError:
        location = None

    location_description = (
        property_obj.detail_values.filter(property_group_detail__detail__slug='locationDescription').first() or ""
    )
    try:
        location_description = location_description.value
    except AttributeError:
        location_description = None

    if location or location_description:
        space += "\nLOCATION\n"
        space += f"{html_to_formatted_text(location_description)}\n" if location_description else ""
        space += f"{html_to_formatted_text(location)}\n" if location else ""

    activities = property_obj.detail_values.filter(property_group_detail__detail__slug='activities').first() or ""
    try:
        activities = activities.value
    except AttributeError:
        activities = None
    if activities:
        space += "\nACTIVITIES AVAILABLE ON-SITE OR NEARBY\n"
        space += f"{html_to_formatted_text(activities)}\n"

    additional_services = (
        property_obj.detail_values.filter(property_group_detail__detail__slug='additionalServices').first() or ""
    )
    try:
        additional_services = additional_services.value
    except AttributeError:
        additional_services = None
    if additional_services:
        space += "\nADDITIONAL SERVICES\n"
        space += f"{html_to_formatted_text(additional_services)}\n"
    return space


def format_house_rules(property_obj):
    house_rules = ""

    rental_prices = (
        property_obj.detail_values.filter(property_group_detail__detail__slug='rentalPriceIncludes').first() or ""
    )
    try:
        rental_prices = rental_prices.value
    except AttributeError:
        rental_prices = None
    if rental_prices:
        house_rules += "\nRENTAL PRICE INCLUDES\n"
        house_rules += f"{html_to_formatted_text(rental_prices)}\n"

    know_before_you_go = (
        property_obj.detail_values.filter(property_group_detail__detail__slug='knowBeforeYouGo').first() or ""
    )
    try:
        know_before_you_go = know_before_you_go.value
    except AttributeError:
        know_before_you_go = None
    if know_before_you_go:
        house_rules += "\nKNOW BEFORE YOU GO\n"
        house_rules += f"{html_to_formatted_text(know_before_you_go)}\n"

    staff_services = (
        property_obj.detail_values.filter(property_group_detail__detail__slug='staffServices').first() or ""
    )
    try:
        staff_services = staff_services.value
    except AttributeError:
        staff_services = None
    if staff_services:
        house_rules += "\nSTAFF AND SERVICES\n"
        house_rules += f"{html_to_formatted_text(staff_services)}\n"

    kids_services = property_obj.detail_values.filter(property_group_detail__detail__slug='kidsServices').first() or ""
    try:
        kids_services = kids_services.value
    except AttributeError:
        kids_services = None
    if kids_services:
        house_rules += "\nKIDS SERVICES\n"
        house_rules += f"{html_to_formatted_text(kids_services)}\n"

    pet_policy = property_obj.detail_values.filter(property_group_detail__detail__slug='petPolicy').first() or ""
    try:
        pet_policy = pet_policy.value
    except AttributeError:
        pet_policy = None
    if pet_policy:
        house_rules += "\nPET POLICY\n"
        house_rules += f"{html_to_formatted_text(pet_policy)}\n"
    return house_rules


def build_update_payload(property_obj, hostify_api, sync_calendars=False):
    field_values = {
        'cleaning_fee_value': None,
        'security_deposit_value': None,
        'guests_included_value': None,
        'smoking_allowed_value': None,
        'pets_allowed_value': None,
        'checkin_start_value': None,
        'checkout_value': None,
    }

    description_values = {
        "interaction": "",
        "notes": "",
        "neighborhood_overview": "",
        "house_manual": "",
        "checkin_place": "",
        "arrival_info": "",
        "transit": "",
        "access": "",
        "summary": "",
    }

    detail_to_field_mapping = {
        'Cleaning Fee': ('cleaning_fee_value', 'value'),
        'SecurityDeposit': ('security_deposit_value', 'value'),
        'Max guests': ('guests_included_value', 'value'),
        'Smoking': ('smoking_allowed_value', 'value'),
        'Pets On Request': ('pets_allowed_value', 'value'),
        'Checkin Time': ('checkin_start_value', 'value'),
        'Checkout Time': ('checkout_value', 'value'),
        'Activities': ('description.interaction', 'value'),
        'Additional Services': ('description.house_manual', 'value'),
        'Instant Booking': ('instant_booking', 'bool_value'),
    }

    for detail_value in property_obj.detail_values.all():
        detail_name = detail_value.property_group_detail.detail.name
        value = getattr(detail_value, 'value', 'N/A')
        if detail_name in detail_to_field_mapping:
            field_path, value_attr = detail_to_field_mapping[detail_name]

            attrs = value_attr.split('.')
            value = detail_value
            for attr in attrs:
                try:
                    value = getattr(value, attr)
                except AttributeError:
                    value = None
                    break

            if value is None:
                continue

            if field_path.startswith('description.'):
                desc_key = field_path.split('.')[1]
                if description_values[desc_key]:
                    description_values[desc_key] += '\n' + html_to_formatted_text(str(value))
                else:
                    description_values[desc_key] = html_to_formatted_text(str(value))
            else:
                field_values[field_path] = html_to_formatted_text(str(value))

    def convert_decimals(obj):
        if isinstance(obj, dict):
            return {k: convert_decimals(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_decimals(element) for element in obj]
        elif isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, DetailOption):
            return obj.name
        elif hasattr(obj, 'name'):
            return obj.name
        else:
            return obj

    def strip_seconds(time_input):
        if isinstance(time_input, str):
            parts = time_input.split(':')
            if len(parts) >= 2:
                return f"{parts[0]}:00"
            else:
                return time_input
        elif isinstance(time_input, time):
            return time_input.strftime('%H') + ':00'
        else:
            return ''

    checkin_start_raw = field_values.get('checkin_start_value')
    checkout_raw = field_values.get('checkout_value')

    checkin_start = strip_seconds(checkin_start_raw) if checkin_start_raw else ''
    checkout = strip_seconds(checkout_raw) if checkout_raw else ''

    amenities_list = list(property_obj.amenities.values_list('name', flat=True))
    description_values['space'] = format_space_data(property_obj)
    description_values['house_rules'] = format_house_rules(property_obj)
    hostify_summary = (
        property_obj.detail_values.filter(property_group_detail__detail__slug='hostifySummary').first() or ""
    )
    try:
        hostify_summary = hostify_summary.value
    except AttributeError:
        hostify_summary = None
    description_values['summary'] = f"{html_to_formatted_text(hostify_summary)}\n" if hostify_summary else ""

    try:
        pet_fee = property_obj.detail_values.filter(property_group_detail__detail__slug='petFee').first().value
        if pet_fee:
            pet_fee = float(json.loads(pet_fee).get('value', 0)) or 0
    except (AttributeError, TypeError, ValueError):
        pet_fee = 0
    except Exception as e:
        logger.exception(f'Error when getting pet fee for property {property_obj.id} - {e}')
    try:
        cleaning_fee = (
            property_obj.detail_values.filter(property_group_detail__detail__slug='cleaningFee').first().value
        )
        if cleaning_fee:
            cleaning_fee = int(float(json.loads(cleaning_fee).get('value', 0))) or 0
    except (AttributeError, TypeError, ValueError):
        cleaning_fee = 0
    except Exception as e:
        logger.exception(f'Error when getting cleaning fee for property {property_obj.id} - {e}')
    try:
        security_deposit = (
            property_obj.detail_values.filter(property_group_detail__detail__slug='securityDeposit').first().value
        )
        if security_deposit is not None:
            security_deposit = int(float(json.loads(security_deposit).get('value', 0))) or 0
    except (AttributeError, TypeError, ValueError):
        security_deposit = 0
    except Exception as e:
        logger.exception(f'Error when getting security deposit for property {property_obj.id} - {e}')

    try:
        service_pms = int(is_property_active(property_obj))
    except Exception:
        service_pms = 0

    update_data = {
        "listing_id": property_obj.hostify_id,
        "nickname": (
            f"{property_obj.name} - {property_obj.title}"
            if getattr(property_obj, 'title', '') and getattr(property_obj, 'name', '')
            else getattr(property_obj, 'title', '') or getattr(property_obj, 'name', '')
        ),
        "pets_fee": pet_fee,
        "cleaning_fee": cleaning_fee,
        "security_deposit": security_deposit,
        "pets_allowed": (
            1 if getattr(field_values.get('pets_allowed_value'), 'name', '').lower() == 'pets allowed' else 0
        ),
        "smoking_allowed": (
            1 if getattr(field_values.get('smoking_allowed_value'), 'name', '').lower() == 'smoking allowed' else 0
        ),
        "listing_type": "entire home",
        "property_type_group": "houses",
        "property_type": "House",
        "default_daily_price": property_obj.default_price or 0,
        "description": description_values,
        "amenities": amenities_list,
        "service_pms": service_pms,
    }

    if field_values.get('instant_booking') == "everyone":
        update_data["instant_booking"] = "everyone"

    if property_obj.property_type and property_obj.property_type.name.capitalize() in VALID_PROPERTY_TYPES:
        update_data["property_type"] = property_obj.property_type.name.lower()

    if field_values.get('guests_included_value'):
        update_data["guests_included"] = field_values['guests_included_value']

    if checkin_start:
        update_data["checkin_start"] = '24:00' if checkin_start == '00:00' else checkin_start

    if checkout:
        update_data["checkout"] = f'{checkout[:2]}:00' if checkout == '00:00' else checkout

    update_data_serializable = convert_decimals(update_data)

    return update_data_serializable


def sync_property_with_hostify(property_obj, update_data_serializable, sync_calendars, hostify_api):
    response = hostify_api.update_listing(property_obj.hostify_id, update_data_serializable)

    if not response.get('success', False):
        raise Exception(
            f"""
            Failed to update listing for property {property_obj.name}

            Response
            {response}

            Payload
            {pprint.pformat(update_data_serializable, indent=1)}
        """
        )

    unsynced_photos = property_obj.photos.filter(is_synched=False)

    for photo in unsynced_photos:
        try:
            photo_url = [photo.image.url]
            sync_photos(property_obj, photo_url, hostify_api)
            photo.is_synched = True
            photo.save()
        except Exception as e:
            logger.error(f"Failed to sync photo {photo.id}: {e}")

    # rooms = property_obj.bedrooms_configurations.all()
    # sync_rooms(property_obj, rooms, hostify_api)

    enable_listing = property_obj.is_active
    toggle_listing_status(property_obj, enable_listing, hostify_api)

    if sync_calendars:
        try:
            currency = (
                property_obj.prop.detail_values.filter(property_group_detail__detail__slug='currency').first().value
            )
        except AttributeError:
            currency = 'EUR'
        restrictions_payload = {
            "listing_id": property_obj.hostify_id,
            "price": property_obj.default_price or 0,
            "occupancy": 1,
            "currency": currency or "EUR",
        }
        hostify_api.process_booking_restrictions(restrictions_payload)
        PropertyCalendar.objects.filter(property=property_obj).delete()
        PropertyCalendar.objects.bulk_create(
            [
                PropertyCalendar(
                    property=property_obj,
                    date=date,
                    status=CalendarStatusChoices.AVAILABLE,
                )
                for date in (date.today() + timedelta(days=i) for i in range(365))
            ]
        )
    else:
        start_date = date.today()
        end_date = date.today() + timedelta(days=365)
        response = hostify_api.get_listing_calendar(property_obj.hostify_id, start_date, end_date)
        PropertyCalendar.objects.filter(property=property_obj).delete()
        calendars = [
            PropertyCalendar(
                property=property_obj,
                date=calendar['date'],
                status=calendar['status'],
                hostify_id=calendar['id'],
                price=calendar['price'],
                note=calendar['note'],
            )
            for calendar in response['calendar']
        ]
        PropertyCalendar.objects.bulk_create(calendars)
    return response


def sync_properties_data():
    hostify_api = HostifyAPI()
    response = hostify_api.get_listings()

    if response.get('success', False):
        properties_data = response.get('listings', [])
        for property_data in properties_data:
            try:
                sync_property_with_hostify(property_data, hostify_api)
            except Exception as e:
                logger.error(f"Failed to sync property {property_data.get('name', '')}: {e}")
    else:
        logger.error(f'Failed to fetch data from Hostify API: {response}')


def upsert_hostify_calendar(data: dict):
    from apps.properties.models import Property

    if not data.get('checkOut'):
        dates = [data['checkIn']]
    else:
        dates = [data['checkIn'] + timezone.timedelta(days=i) for i in range((data['checkOut'] - data['checkIn']).days)]
    property = Property.objects.get(hostify_id=data['listing_id'])
    status = (
        CalendarStatusChoices.AVAILABLE
        if data['status'] in AVAILABLE_CALENDAR_RESERVATION_STATUS_MAPPING
        else CalendarStatusChoices.BOOKED
    )

    with transaction.atomic():
        for _date in dates:
            payload = {
                'date': _date,
                'hostify_id': data['id'],
                'note': data['notes'],
                'status': status,
            }
            calendar = PropertyCalendar.objects.filter(property=property, date=_date)

            if calendar:
                calendar.update(**payload)
            else:
                PropertyCalendar.objects.create(property=property, **payload)


def process_fee_data(fees: list, property_price: float = 0):
    original_price = property_price
    taxable_percent = []
    non_taxable_amounts = []
    non_taxable_percents = []
    processed_fee_list = []
    pending_percent_fee_list_indexes = []
    remaining_sum_by_night = 0
    for fee in fees:
        amount = fee.get('amount', 0)
        if not amount:
            continue
        processed_fee = {**fee, 'processed_amount': 0, 'multiply_by_stay_period': False}
        if fee['taxable']:
            if fee['charge_type'] == 'Percent':
                taxable_percent.append(fee['amount'])
                calculated_price = original_price * fee['amount'] / 100
                property_price += calculated_price
                processed_fee['processed_amount'] = calculated_price
                processed_fee_list.append(processed_fee)
                continue
            elif fee['charge_type'] == 'Per Night':
                processed_fee['processed_amount'] = fee['amount']
                processed_fee['multiply_by_stay_period'] = True
                remaining_sum_by_night += fee['amount']
                continue
            property_price += fee['amount']
            processed_fee['processed_amount'] = fee['amount']
            processed_fee_list.append(processed_fee)
        else:
            if fee['charge_type'] == 'Percent':
                non_taxable_percents.append(fee['amount'])
                processed_fee_list.append(processed_fee)
                pending_fee_index = len(processed_fee_list) - 1 if len(processed_fee_list) else 0
                pending_percent_fee_list_indexes.append(pending_fee_index)
                continue
            non_taxable_amounts.append(fee['amount'])
            processed_fee_list.append(processed_fee)
            processed_fee['processed_amount'] = fee['amount']
    for pending_fee_index in pending_percent_fee_list_indexes:
        try:
            fee_to_process = processed_fee_list[pending_fee_index]
            if fee['amount']:
                calculated_price = original_price * fee_to_process.get('amount', 0) / 100
            else:
                calculated_price = fee_to_process.get('amount', 0)
            fee_to_process['processed_amount'] = calculated_price
            property_price += calculated_price
        except IndexError:
            continue
    for non_taxable_amount in non_taxable_amounts:
        property_price += non_taxable_amount
    return {
        'property_price': property_price,
        'remaining_sum_by_night': remaining_sum_by_night,
        'processed_fee_list': processed_fee_list,
    }


def get_fees_from_cache(hostify_id: str):
    try:
        with RedisContextManager() as r:
            fees = r.get(f"hostify:fees:{str(hostify_id)}")
            if fees:
                return json.loads(fees)
    except Exception:
        pass


def set_fees_to_cache(hostify_id: str, fees: list):
    try:
        with RedisContextManager() as r:
            r.set(f"hostify:fees:{str(hostify_id)}", json.dumps(fees), ex=3600)
    except Exception:
        pass


def get_fees_from_hostify(hostify_api, hostify_id: str):
    cache_fees = get_fees_from_cache(hostify_id)
    if cache_fees:
        return
    property = Property.objects.filter(hostify_id=hostify_id).first()
    db_tax = PropertyTax.objects.filter(property=property).first()
    if db_tax and not db_tax.is_stale():
        return

    fee_request = hostify_api.get_listing_fees(hostify_id)
    fees = fee_request.get('fees', [])
    set_fees_to_cache(hostify_id, fees)
    if db_tax:
        db_tax.tax_object = fees
        db_tax.save()
        return
    PropertyTax.objects.create(property=property, tax_object=fees)


def update_property_price(hostify_api, price, start_date, end_date, hostify_id):
    today = date.today()
    formatted_today = timezone.datetime.strftime(today, '%Y-%m-%d')
    start_date_obj = timezone.datetime.strptime(start_date, '%Y-%m-%d').date()
    end_date_obj = timezone.datetime.strptime(end_date, '%Y-%m-%d').date()
    if start_date_obj < today:
        start_date = formatted_today
    if end_date_obj < today:
        end_date = formatted_today

    hostify_api.update_listing_price(price, start_date, end_date, hostify_id)
