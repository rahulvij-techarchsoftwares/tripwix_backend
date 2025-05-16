import calendar
import functools
import time
from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib import admin
from django.core.cache import cache
from django.db import connection, reset_queries
from hashid_field import Hashid
from modeltrans.conf import get_available_languages
from modeltrans.utils import build_localized_fieldname

from .query import FakeQuerySet


class ValidContentTypes:
    def __init__(self, ignore_list=[], is_searchable=False):
        self.ignore_list = ignore_list
        self.searchable = is_searchable

    def all(self):
        return FakeQuerySet(self.fetch())

    def fetch(self):
        from django.contrib.contenttypes.models import ContentType

        for content_type in ContentType.objects.all():
            model_class = content_type.model_class()
            if model_class in self.ignore_list:
                continue
            if self.searchable:
                try:
                    model_admin = admin.site._registry[model_class]
                except KeyError as e:
                    continue
                if not model_admin.get_search_fields(None):
                    continue
            if model_class and hasattr(model_class, 'get_model_serializer'):
                yield content_type


def get_default_lang():
    default_lang = getattr(settings, "LANGUAGE_CODE", "en")
    return default_lang.lower() if default_lang else "en"


def generate_hashid(id, min_length=7):
    salt = getattr(settings, 'HASHID_FIELD_SALT', settings.SECRET_KEY)
    return Hashid(int(id), min_length=min_length, salt=salt)


def build_lang_url(lang=None, url='', trans_url={}):
    if lang:
        url = f'/{lang}/{trans_url.get(lang, url)}'
    return url


def domain_with_proto(url=''):
    from django.contrib.sites.models import Site

    project_url = getattr(settings, 'PROJECT_URL', None)
    if project_url is not None:
        return f'{project_url}{url}'

    # fallback using sites
    current_site = Site.objects.get_current()
    domain = current_site.domain
    if domain.startswith('http'):
        return f'{domain}{url}'

    # fallback to https
    proto = 'https://'
    return f'{proto}{domain}{url}'


def get_translation_fields(field):
    return [build_localized_fieldname(field, lang) for lang in get_available_languages()]


def _join_css_class(bits, offset):
    if '-'.join(bits[-offset:]) in get_available_languages():
        return '%s-%s' % ('_'.join(bits[: len(bits) - offset]), '_'.join(bits[-offset:]))
    return ''


def build_css_class(localized_fieldname, prefix=''):
    """
    Returns a css class based on ``localized_fieldname`` which is easily
    splittable and capable of regionalized language codes.

    Takes an optional ``prefix`` which is prepended to the returned string.
    """
    bits = localized_fieldname.split('_')
    css_class = ''
    if len(bits) == 1:
        css_class = str(localized_fieldname)
    elif len(bits) == 2:
        # Fieldname without underscore and short language code
        # Examples:
        # 'foo_de' --> 'foo-de',
        # 'bar_en' --> 'bar-en'
        css_class = '-'.join(bits)
    elif len(bits) > 2:
        # Try regionalized language code
        # Examples:
        # 'foo_es_ar' --> 'foo-es_ar',
        # 'foo_bar_zh_tw' --> 'foo_bar-zh_tw'
        css_class = _join_css_class(bits, 2)
        if not css_class:
            # Try short language code
            # Examples:
            # 'foo_bar_de' --> 'foo_bar-de',
            # 'foo_bar_baz_de' --> 'foo_bar_baz-de'
            css_class = _join_css_class(bits, 1)
    return '%s-%s' % (prefix, css_class) if prefix else css_class


def get_month_start_end():
    now = datetime.now()

    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_end = (month_start + relativedelta(months=1)) - timedelta(seconds=1)

    return month_start, month_end


def generate_calendar(month_start):
    month = month_start.month
    year = month_start.year

    cal = calendar.Calendar(firstweekday=6)
    month_days = cal.monthdayscalendar(year, month)
    return month_days


def clear_cache() -> None:
    """
    Clear cache from Redis.

    :return: None
    """
    from apps.core.services import RedisContextManager

    with RedisContextManager() as r:
        r.flushdb()


def clear_cache_for_keys(keys: list) -> None:
    from apps.core.services import RedisContextManager

    with RedisContextManager() as redis:
        redis.delete(*keys)


def query_debugger(func):
    """
    This decorator will print the number of queries executed and the time taken in the console.
    """

    @functools.wraps(func)
    def inner_func(*args, **kwargs):
        reset_queries()

        start_queries = len(connection.queries)

        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()

        end_queries = len(connection.queries)

        print(f"Function : {func.__name__}")
        print(f"Number of Queries : {end_queries - start_queries}")
        print(f"Finished in : {(end - start):.2f}s")
        return result

    return inner_func
