from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ComponentFormsConfig(AppConfig):
    name = 'apps.component_forms'
    label = 'component_forms'
    verbose_name = _("Forms")
