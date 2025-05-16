from django.apps import AppConfig
from django.utils.module_loading import autodiscover_modules
from django.utils.translation import gettext_lazy as _


def autodiscover():
    from apps.email import definitions

    autodiscover_modules('emails', register_to=definitions)


class EmailAppConfig(AppConfig):
    name = 'apps.email'
    label = "def_email"
    verbose_name = _("Email")

    def ready(self):
        super().ready()
        autodiscover()
