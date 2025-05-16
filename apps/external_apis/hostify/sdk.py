import logging

import requests
from django.conf import settings

from apps.external_apis.logger.error_logger import ErrorLoggerHandler


class HostifyAPI:
    error_logger = ErrorLoggerHandler(logging.getLogger('hostify_logger'))
    base_url = 'https://api-rms.hostify.com'
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'x-api-key': settings.HOSTIFY_API_TOKEN,
    }

    def request_handler(self, method, endpoint, data=None, params=None, ignore_exception_codes: list[int] = None):
        try:
            url = self.base_url + endpoint
            headers = self.headers
            response = requests.request(method, url, headers=headers, json=data, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as error:
            if ignore_exception_codes and error.response.status_code in ignore_exception_codes:
                return {"success": False, "error": str(error)}
            self.error_logger.log_error(error)
            return {"success": False, "error": str(error)}

    def get_listings(self):
        return self.request_handler('GET', '/listings/')

    def update_listing(self, listing_id, data):
        return self.request_handler('POST', '/listings/update', data=data)

    def create_listing(self, data):
        return self.request_handler('POST', '/listings/process_location', data=data)

    def get_listing_details(self, listing_id):
        return self.request_handler('GET', f'/listings/{listing_id}')

    def list_unlist_property(self, listing_id, channel_listed):
        return self.request_handler(
            'POST', '/listings/channel_list', data={'listing_id': listing_id, 'channel_listed': channel_listed}
        )

    def process_photos(self, listing_id, photos=list()):
        return self.request_handler(
            'POST', '/listings/process_photos', data={'listing_id': listing_id, 'photos': photos}
        )

    def process_rooms(self, listing_id, rooms):
        return self.request_handler('POST', '/listings/process_layout', data={'listing_id': listing_id, 'rooms': rooms})

    def process_amenities(self, listing_id, amenities):
        return self.request_handler(
            'POST', '/listings/process_amenities', data={'listing_id': listing_id, 'amenities': amenities}
        )

    def process_booking_restrictions(self, data):
        return self.request_handler('POST', '/listings/process_booking_restrictions', data)

    def get_listing_calendar(self, listing_id, start_date, end_date, page=1):
        return self.request_handler(
            'GET',
            '/calendar',
            params={'listing_id': listing_id, 'start_date': start_date, 'end_date': end_date, 'page': page},
        )

    def get_listing_fees(self, listing_id):
        return self.request_handler('GET', f'/listings/listing_fees/{listing_id}', ignore_exception_codes=[404])

    def update_listing_price(self, price: float, start_date: str, end_date: str, listing_id: int):
        return self.request_handler(
            'PUT',
            '/calendar',
            data={'price': price, 'start_date': start_date, 'end_date': end_date, 'listing_id': listing_id},
        )
