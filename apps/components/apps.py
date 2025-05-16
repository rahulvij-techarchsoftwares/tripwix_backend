from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ComponentsConfig(AppConfig):
    name = 'apps.components'
    label = 'components'
    verbose_name = _("Components")
