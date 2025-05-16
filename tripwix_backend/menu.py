from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django_admin_kubi.admin_menu.items import MenuItem, ModelItem, ModelList
from django_admin_kubi.admin_menu.menu import Menu

admin_models = ("django.contrib.auth.*", 'apps.users.models.WebsiteUser')


class MyAdminMenu(Menu):
    dashboard = MenuItem(title=_('Dashboard'), url=reverse('admin:index'), icon="fa-th-large")

    properties = ModelItem(model=("apps.properties.models.Property"), icon="fa-home")
    users = ModelList(_('Administration'), models=admin_models, icon="fa-user")

    settings = ModelList(
        _('Settings'),
        models=(
            'apps.properties.models.Detail',
            'apps.locations.models.Location',
            'apps.locations.models.SubLocation',
            'apps.properties.models.PropertyGroup',
            'apps.properties.models.PropertyType',
            'apps.properties.models.PropertyTypology',
            'apps.properties.models.PropertyDivision',
            'apps.properties.models.PropertyOwnership',
            'apps.properties.models.Amenity',
        ),
        icon="fa-cogs",
    )
