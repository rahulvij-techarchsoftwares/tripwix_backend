import time

import boto3
from celery import shared_task
from django.conf import settings
from django.core.files.base import ContentFile
from googleapiclient.errors import HttpError as GoogleHttpError

from apps.properties.utils import ExchangeRateService
from apps.tools.google_drive_api import GoogleDriveApi
from tripwix_backend.celery import app

from .models import Property, PropertyMediaPhoto


@app.task
def refresh_google_webhook():
    google_drive = GoogleDriveApi()
    google_drive.register_google_webhook()


@app.task
def fetch_images_from_google_drive(property_id: str):
    prop = Property.objects.filter(id=property_id).first()

    if prop is None:
        return

    google_drive = GoogleDriveApi()
    folder_id = prop.get_drive_folder()
    media_photo_list = list()

    try:
        images = google_drive.get_google_drive_images(folder_id)
    except GoogleHttpError:
        return

    session = boto3.Session(
        aws_access_key_id=settings.STORAGES["default"]["OPTIONS"]["access_key"],
        aws_secret_access_key=settings.STORAGES["default"]["OPTIONS"]["secret_key"],
        region_name=settings.STORAGES["default"]["OPTIONS"]["region_name"],
    )
    s3 = session.resource("s3")
    bucket = s3.Bucket(settings.STORAGES["default"]["OPTIONS"]["bucket_name"])

    objects_to_deleted = bucket.objects.filter(Prefix=f"uploads/{prop.reference}/")
    if len(list(objects_to_deleted)) > 0:
        bucket.delete_objects(Delete={"Objects": [{"Key": obj.key} for obj in objects_to_deleted]})
        prop.photos.clear()

    for image in images:
        mime_type = image.get("mimeType")
        if "image" not in mime_type:
            continue

        media_photo = PropertyMediaPhoto()
        file_id = image.get("id")
        name = image.get("name", f"{file_id}")

        try:
            order = int(name.split("-")[-1].split(".")[0])
        except ValueError:
            order = 999  # place a high value on order, might be an unintended picture

        media_photo.order = order
        image_bytes = google_drive.download_google_drive_image(file_id)
        media_photo.image.save(f"{prop.reference}/{name}", ContentFile(image_bytes), save=False)
        media_photo_list.append(media_photo)
        time.sleep(0.5)  # to be safe from google api rate limit

    photos = PropertyMediaPhoto.objects.bulk_create(media_photo_list)

    prop.photos.set(photos)
    prop.standard_photos_synced = True
    prop.save(update_fields=["standard_photos_synced"])


@app.task
def task_sync_with_hostify(property_id):
    from celery.result import AsyncResult
    from celery.states import UNREADY_STATES

    from apps.core.services import RedisContextManager
    from apps.hostify.tasks import task_sync_property_with_hostify
    from apps.properties.choices import SyncStatusChoices
    from apps.properties.models import Property

    property_obj = Property.objects.get(id=property_id)

    if not property_obj.ready_to_sync or property_obj.sync_status == SyncStatusChoices.SYNCING:
        return

    with RedisContextManager() as r:
        result_id = r.get(f"lock:property_hostify_sync:{property_id}")
        if result_id:
            task_result = AsyncResult(result_id)
            if task_result and task_result.state in UNREADY_STATES:
                return
            r.delete(f"lock:property_hostify_sync:{property_id}")
        result_id = task_sync_property_with_hostify.apply_async((property_id,), countdown=10)
        r.set(f"lock:property_hostify_sync:{property_id}", str(result_id), ex=3900)


@app.task
def task_construct_next_payload(property_id):
    from celery.result import AsyncResult
    from celery.states import UNREADY_STATES

    from apps.core.services import RedisContextManager
    from apps.external_apis.hostify.sdk import HostifyAPI
    from apps.hostify.utils import build_update_payload, create_property_with_hostify
    from apps.properties.choices import SyncStatusChoices
    from apps.properties.models import Property

    with RedisContextManager() as r:
        payload_build_task_result = r.get(f"lock:property_hostify_payload_build:{property_id}")
        if payload_build_task_result:
            try_count = 0
            while try_count < 30:
                task_result = AsyncResult(payload_build_task_result)
                if task_result and task_result.state in UNREADY_STATES:
                    time.sleep(5)
                    try_count += 1
                    continue
                break
            r.delete(f"lock:property_hostify_payload_build:{property_id}")
        r.set(f"lock:property_hostify_payload_build:{property_id}", "1", ex=200)
        property_obj = Property.objects.get(id=property_id)
        hostify_api = HostifyAPI()
        is_new_property = False
        changes_to_sync = property_obj.changes_to_sync
        needs_calendar = False
        if not property_obj.hostify_id:
            needs_calendar = True
            is_new_property = True
        if is_new_property:
            create_property_with_hostify(property_obj, hostify_api)

        payload = build_update_payload(property_obj, hostify_api, is_new_property)
        if not payload:
            return

        if property_obj.sync_status == SyncStatusChoices.SYNCING:
            wait_count = 0
            while wait_count < 30:
                time.sleep(5)
                property_obj.refresh_from_db()
                if property_obj.sync_status != SyncStatusChoices.SYNCING:
                    break
                wait_count += 1
        if not changes_to_sync:
            changes_to_sync = payload
        else:
            changes_to_sync.update(payload)
        sync_status = (
            SyncStatusChoices.SYNC_PENDING
            if property_obj.changes_to_sync != property_obj.last_synced_payload
            else SyncStatusChoices.SYNCED
        )
        Property.objects.filter(id=property_id).update(
            changes_to_sync=changes_to_sync,
            needs_calendar_creation=needs_calendar,
            sync_status=sync_status,
        )
        r.delete(f"lock:property_hostify_payload_build:{property_id}")


@app.task
def task_update_listing_price(price, start_date, end_date, hostify_id):
    from apps.external_apis.hostify.sdk import HostifyAPI
    from apps.hostify.utils import update_property_price

    hostify_api = HostifyAPI()
    update_property_price(hostify_api, price, start_date, end_date, hostify_id)


@shared_task
def fetch_exchange_rates_task():
    ExchangeRateService.update_exchange_rates()
