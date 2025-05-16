import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def task_sync_all_properties():
    from apps.external_apis.hostify.sdk import HostifyAPI  # Importando a classe HostifyAPI
    from apps.hostify.utils import sync_property_with_hostify
    from apps.properties.models import Property

    hostify_api = HostifyAPI()  # Criando uma instância do HostifyAPI
    properties_data = Property.objects.all()

    for property_data in properties_data:
        sync_property_with_hostify(property_data, hostify_api)
    logger.info(f'Successfully synced property: {property_data.id}')


@shared_task
def task_sync_property_with_hostify(property_id):
    from apps.core.services import RedisContextManager
    from apps.external_apis.hostify.sdk import HostifyAPI
    from apps.hostify.utils import is_property_active, sync_property_with_hostify
    from apps.properties.choices import SyncStatusChoices
    from apps.properties.models import Property

    try:
        hostify_api = HostifyAPI()
        property_obj = Property.objects.get(id=property_id)
        last_payload = property_obj.last_synced_payload or {}
        changes_payload = property_obj.changes_to_sync or {}
        update_payload = {}
        for key in changes_payload.keys():
            if key in last_payload.keys() and last_payload[key] == changes_payload[key]:
                continue
            update_payload[key] = changes_payload[key]
        if not update_payload:
            Property.objects.filter(id=property_id).update(
                sync_status=SyncStatusChoices.SYNCED, last_synced_at=timezone.now(), changes_to_sync={}
            )
            return
        update_payload['listing_id'] = property_obj.hostify_id
        update_payload['service_pms'] = int(is_property_active(property_obj))

        Property.objects.filter(id=property_id).update(
            sync_status=SyncStatusChoices.SYNCING, last_synced_payload=update_payload
        )
        sync_property_with_hostify(property_obj, update_payload, property_obj.needs_calendar_creation, hostify_api)
        Property.objects.filter(id=property_id).update(
            sync_status=SyncStatusChoices.SYNCED, last_synced_at=timezone.now(), changes_to_sync={}
        )
        logger.info(f'Successfully synced property: {property_obj.id}')
    except Exception as e:
        property_obj.sync_status = SyncStatusChoices.SYNC_FAILED
        logger.exception(f'Error syncing property: {property_id}. Error: {e}')
    finally:
        with RedisContextManager() as r:
            r.delete(f'lock:property_hostify_sync:{str(property_id)}')


@shared_task
def task_process_calendar_webhook(data):
    from apps.hostify.utils import upsert_hostify_calendar

    if data.get('checkIn'):
        data['checkIn'] = timezone.datetime.strptime(data['checkIn'], '%Y-%m-%d')
    if data.get('checkOut'):
        data['checkOut'] = timezone.datetime.strptime(data['checkOut'], '%Y-%m-%d')
    upsert_hostify_calendar(data)
    logger.info(f'Successfully processed webhook: {data}')


@shared_task
def task_get_fees_data():
    from apps.external_apis.hostify.sdk import HostifyAPI
    from apps.hostify.utils import get_fees_from_hostify
    from apps.properties.models import Property

    hostify_api = HostifyAPI()
    for property_data in Property.objects.published():
        try:
            hostify_id = property_data.hostify_id
            if not hostify_id:
                continue
            get_fees_from_hostify(hostify_api, hostify_id)
        except Exception as e:
            logger.exception(f'Error syncing fees for property: {property_data.id}. Error: {e}')
    logger.info('Successfully synced fees data')
