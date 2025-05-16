import requests
from celery import shared_task
from django.conf import settings


@shared_task
def clear_cache_task():
    # from apps.content.utils import clear_api_struct_cache
    from apps.pages.utils import clear_api_page_cache

    clear_api_page_cache()
    # clear_api_struct_cache()

    # call frontend clear cache webhook
    clear_cache_webhook_url = getattr(settings, 'CLEAR_CACHE_WEBHOOK_URL', None)
    if clear_cache_webhook_url:
        requests.get(clear_cache_webhook_url)
