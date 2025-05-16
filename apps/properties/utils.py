import logging
from decimal import Decimal
from re import sub

import requests
from django.apps import apps
from django.db import transaction
from django.utils import timezone
from django.utils.html import format_html
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from apps.properties.choices import SyncStatusChoices


def get_publication_status(obj):
    """
    Return publication status and url when available
    :param obj:
    :return:
    """
    from django.contrib.humanize.templatetags.humanize import naturaltime

    url = None
    if hasattr(obj, "get_absolute_url"):
        try:
            url = obj.get_absolute_url()
        except Exception:
            pass

    link_label = "view"
    output = "Published"
    if not obj.is_active:
        link_label = "preview"
        output = "Unpublished"
    elif obj.publication_date and obj.publication_date > timezone.now():
        link_label = "preview"
        output = "To be published %s" % naturaltime(obj.publication_date)

    if url:
        link = ', <a href="%s">%s</a>' % (url, link_label)
    else:
        link = ""
    return "%s%s" % (output, link)


def get_sync_status(obj):
    sync_status_html = {
        SyncStatusChoices.SYNCED: format_html('<i class="fas fa-check-circle text-success"></i>'),
        SyncStatusChoices.NOT_SYNCED: format_html('<i class="fas fa-times-circle text-danger"></i>'),
        SyncStatusChoices.SYNCING: format_html('<i class="fas fa-sync-alt text-warning"></i>'),
        SyncStatusChoices.SYNC_FAILED: format_html('<i class="fas fa-times-circle text-danger"></i>'),
        SyncStatusChoices.SYNC_PENDING: format_html('<i class="fas fa-exclamation-circle text-warning"></i>'),
    }
    if not obj.sync_status or obj.sync_status not in sync_status_html:
        return format_html(
            '<p><i class="fas fa-question-circle text-secondary"></i> {status}</p>', status=obj.sync_status
        )
    return format_html(
        '<p>{icon} {status}</p>',
        icon=sync_status_html[obj.sync_status],
        status=SyncStatusChoices(obj.sync_status).label,
    )


def sync_property_button(obj):
    if obj.sync_status == SyncStatusChoices.SYNCED:
        return format_html(
            '<button type="button" class="btn btn-sm btn-secondary" disabled><i class="fas fa-sync"></i> Synced</button>'
        )
    return format_html(
        '<button type="button" class="btn btn-sm btn-primary" data-toggle="modal" data-target="#syncPropertyModal" data-id="{id}"><i class="fas fa-sync"></i> Sync</button>',
        id=obj.id,
    )


class PropertyBuilder(object):
    @staticmethod
    def convert_to_camel_case(data_str):
        camel_case = sub(r"(_|-|/|%|&|\(|\))+", " ", data_str).title().replace(" ", "")
        return camel_case[0].lower() + camel_case[1:]

    @staticmethod
    def properties_json_builder(headers, property_data):
        json = dict()
        for i in range(len(property_data)):
            json[headers[i]] = property_data[i]
        return json

    def build(self, data):
        """
        Build a list of properties
        :param data:
        :return:
        """
        headers_list = data[0].split("\t")
        headers = [self.convert_to_camel_case(header) for header in headers_list]
        return [self.properties_json_builder(headers, row.split("\t")) for row in data[1:] if row.split("\t")[5] != ""]


def get_property_calendars(hostify_id, start_date, end_date):
    from apps.external_apis.hostify.sdk import HostifyAPI

    hostify_api = HostifyAPI()
    total_availability = []
    response = hostify_api.get_listing_calendar(hostify_id, start_date, end_date)
    processed_days = [
        {
            "hostify_id": calendar['id'],
            "date": calendar['date'],
            "status": calendar['status'],
            "price": calendar["price"],
            "note": calendar['note'],
        }
        for calendar in response.get('calendar', [])
    ]
    total_availability.extend(processed_days)
    next_page_link = response.get('next_page')
    page = 1
    while next_page_link:
        page += 1
        response = hostify_api.get_listing_calendar(hostify_id, start_date, end_date, page)
        next_page_link = response.get('next_page')
        processed_days = [
            {
                "hostify_id": calendar['id'],
                "date": calendar['date'],
                "status": calendar['status'],
                "price": calendar["price"],
                "note": calendar['note'],
            }
            for calendar in response.get('calendar', [])
        ]
        total_availability.extend(processed_days)

    return total_availability


def get_property_availability(obj, start_date, end_date):
    from apps.external_apis.hostify.sdk import HostifyAPI

    hostify_api = HostifyAPI()
    total_availability = []
    response = hostify_api.get_listing_calendar(obj.hostify_id, start_date, end_date)
    processed_days = [
        {"date": calendar['date'], "status": calendar['status']} for calendar in response.get('calendar', [])
    ]
    total_availability.extend(processed_days)
    next_page_link = response.get('next_page')
    page = 1
    while next_page_link:
        page += 1
        response = hostify_api.get_listing_calendar(obj.hostify_id, start_date, end_date, page)
        next_page_link = response.get('next_page')
        processed_days = [
            {"date": calendar['date'], "status": calendar['status']} for calendar in response.get('calendar', [])
        ]
        total_availability.extend(processed_days)

    return total_availability


class ExchangeRateService:
    API_URL = "https://api.frankfurter.app/latest?base=EUR"
    BASE_CURRENCY = 'EUR'
    DESIRED_CURRENCIES = ['USD', 'EUR', 'GBP', 'MXN']
    SYMBOLS = {'USD': '$', 'EUR': '€', 'GBP': '£', 'MXN': 'MXN'}

    @staticmethod
    def update_exchange_rates():
        try:
            session = requests.Session()
            retry = Retry(
                total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"]
            )
            adapter = HTTPAdapter(max_retries=retry)
            session.mount('https://', adapter)

            response = session.get(ExchangeRateService.API_URL, timeout=50)
            response.raise_for_status()
            data = response.json()

            rates_data = data.get('rates', {})
            if not rates_data:
                raise Exception('Exchange rates not returned by the API.')

            Currency = apps.get_model('properties', 'Currency')

            with transaction.atomic():
                for code in ExchangeRateService.DESIRED_CURRENCIES:
                    defaults = {
                        'rate': (
                            Decimal('1.0')
                            if code == ExchangeRateService.BASE_CURRENCY
                            else Decimal(str(rates_data.get(code, 1.0)))
                        ),
                        'last_updated': timezone.now(),
                        'position': 'after' if code == 'MXN' else 'before',
                        'symbol': ExchangeRateService.SYMBOLS.get(code, '?'),
                    }
                    Currency.objects.update_or_create(code=code, defaults=defaults)

            logging.info('Exchange rates updated and stored in the database.')

        except requests.RequestException as e:
            logging.error(f'Error fetching exchange rates: {str(e)}')
        except Exception as e:
            logging.error(f'Error processing exchange rates: {str(e)}')

    @staticmethod
    def get_rates():
        Currency = apps.get_model('properties', 'Currency')
        currencies = Currency.objects.filter(code__in=ExchangeRateService.DESIRED_CURRENCIES)
        rates = {currency.code: currency.rate for currency in currencies}
        return rates
