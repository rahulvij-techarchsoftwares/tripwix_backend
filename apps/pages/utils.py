from django.core.cache import cache


def clear_api_page_cache():
    for cache_key in cache.keys('*api_page*'):
        cache.delete(cache_key)
