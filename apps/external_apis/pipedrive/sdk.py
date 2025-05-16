import logging

import requests
from django.conf import settings

from apps.external_apis.logger.error_logger import ErrorLoggerHandler


class PipedriveAPI:
    error_logger = ErrorLoggerHandler(logging.getLogger('pipedrive_logger'))
    params = {'api_token': settings.PIPEDRIVE_API_TOKEN}
    base_url = 'https://api.pipedrive.com/'
    headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}

    def handler(self, method, endpoint, data=dict(), params=dict(), headers=dict()):
        response = None
        try:
            url = self.base_url + endpoint
            headers.update(self.headers)
            params.update(self.params)
            response = requests.request(method, url, headers=headers, params=params, json=data)
            return response.json()
        except Exception as error:
            if response:
                error = f'{response.status_code} - {response.text} - {error}'
            self.error_logger.log_error(error)
            raise error

    # Persons
    def get_persons(self):
        return self.handler('GET', 'v1/persons')

    # Organizations
    def get_organizations(self):
        return self.handler('GET', 'v1/organizations')

    def get_organization(self, organization_id: int):
        return self.handler('GET', f'v1/organizations/{organization_id}')

    def get_organization_deals(self, organization_id: int, offset: int = 0):
        return self.handler(
            'GET',
            f'v1/organizations/{organization_id}/deals',
            params={'start': offset, 'status': 'won', 'sort': 'add_time ASC'},
        )

    def create_deal(self, deal_data):
        return self.handler('POST', 'v1/deals', data=deal_data)

    def create_person(self, person_data):
        return self.handler('POST', 'v1/persons', data=person_data)

    def get_deal_fields(self):
        return self.handler('GET', 'v1/dealFields')
