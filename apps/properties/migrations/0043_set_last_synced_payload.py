from django.db import migrations


def set_last_synced_payload(apps, schema_editor):
    from apps.external_apis.hostify.sdk import HostifyAPI
    from apps.hostify.utils import build_update_payload
    from apps.properties.choices import SyncStatusChoices

    Property = apps.get_model('properties', 'Property')
    properties = Property.objects.all()
    hostify_api = HostifyAPI()
    for property in properties:
        last_synced_payload = build_update_payload(property, hostify_api)
        Property.objects.filter(id=property.id).update(
            last_synced_payload=last_synced_payload, sync_status=SyncStatusChoices.SYNCED
        )


class Migration(migrations.Migration):

    dependencies = [
        ('properties', '0042_remove_property_tax_id'),
    ]

    operations = [migrations.RunPython(set_last_synced_payload, migrations.RunPython.noop)]
