import json

import requests
from django.conf import settings
from django.urls import reverse

from apps.core.utils import domain_with_proto


class FirebaseDynamicLinksError(Exception):
    pass


class DynamicLinks:
    FIREBASE_API_URL = 'https://firebasedynamiclinks.googleapis.com/v1/shortLinks?key={}'

    def __init__(self, api_key, domain, timeout=10):
        self.api_key = api_key
        self.domain = domain
        self.timeout = timeout
        self.api_url = self.FIREBASE_API_URL.format(self.api_key)

    def generate_dynamic_link(self, link, short=True, params={}):
        payload = dict(
            dynamicLinkInfo=dict(domainUriPrefix=self.domain, link=link),
            suffix=dict(option="SHORT" if short else "UNGUESSABLE"),
        )
        payload['dynamicLinkInfo'].update(params)
        headers = {'Content-type': 'application/json'}
        response = requests.post(self.api_url, json.dumps(payload), headers=headers, timeout=self.timeout)
        data = response.json()

        if not response.ok:
            raise FirebaseDynamicLinksError(data)

        return data['shortLink']


def generate_dynamic_link(link_url: str, params: dict = {}, short: bool = False) -> str:
    """Generates a dynamic link from firebase, useful for deep links

    Do not forget to add FIREBASE_DYNAMIC_LINK to the settings file:

    FIREBASE_DYNAMIC_LINK = {
        'API_KEY': 'secret',
        'DOMAIN_URI': 'https://example.link',
        'ANDROID_PACKAGE_NAME': 'lo.example.id',
        'IOS_BUNDLE_ID': 'lo.example.id',
    }

    Args:
        link_url (str): the link.
        params (dict, optional): parameters used to create the dynamic link. Defaults to {}.
        short (bool, optional): should this be a short or unguessable link. Defaults to False.

    Returns:
        str: the generated firebase link
    """

    dl = DynamicLinks(
        getattr(settings.FIREBASE_DYNAMIC_LINK, 'API_KEY'), getattr(settings.FIREBASE_DYNAMIC_LINK, 'DOMAIN_URI')
    )
    default_params = {
        "androidInfo": {
            "androidPackageName": getattr(settings.FIREBASE_DYNAMIC_LINK, 'ANDROID_PACKAGE_NAME'),
            "androidMinPackageVersionCode": "1",
        },
        "iosInfo": {"iosBundleId": getattr(settings.FIREBASE_DYNAMIC_LINK, 'IOS_BUNDLE_ID')},
    }
    default_params.update(params)
    return dl.generate_dynamic_link(link_url, short=short, params=default_params)


def get_dynamic_link_default_url() -> str:
    return domain_with_proto(reverse(getattr(settings, "DYNAMIC_LINK_DEFAULT_URL_NAME", "web-deeplink")))
