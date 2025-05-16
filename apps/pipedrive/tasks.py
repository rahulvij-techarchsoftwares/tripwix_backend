from celery import shared_task

from apps.pipedrive.utils import (
    process_inquiry_create,
    process_lead_create,
    sync_deals_data,
    sync_organization_data,
    sync_pipedrive_persons,
)


@shared_task
def task_sync_persons():
    sync_pipedrive_persons()


@shared_task
def task_sync_organizations():
    sync_organization_data()


@shared_task
def task_sync_deals(organization_id: int = None):
    sync_deals_data(organization_id)


@shared_task
def task_progressive_countdown_deal_sync():
    from apps.pipedrive.models import Organization

    countdown = 0.1
    for organization in Organization.objects.all():
        task_sync_deals.apply_async((organization.pipedrive_id,), countdown=countdown)


@shared_task
def task_sync_pipedrive_models():
    sync_organization_data()
    task_sync_persons.delay()
    task_progressive_countdown_deal_sync.delay()


@shared_task
def task_process_inquiry_create(inquiry_id):
    process_inquiry_create(inquiry_id)


@shared_task
def task_send_lead_to_pipedrive(lead_id):
    process_lead_create(lead_id)
