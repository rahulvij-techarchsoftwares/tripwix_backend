from django.apps import AppConfig
from django.core import checks
from django.utils.translation import gettext_lazy as _


class HxConfig(AppConfig):
    name = "apps.htmx"
    verbose_name = _("Htmx")
