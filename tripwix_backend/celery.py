from celery import Celery
from celery.schedules import crontab

app = Celery("tripwix_backend")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

'''
app.conf.beat_schedule = {
    "refresh-google-webhook": {
        "task": "apps.properties.tasks.refresh_google_webhook",
        "schedule": 60 * 60,  # 60 minutes
    },
    "sync_pipedrive_users_daily": {
        "task": "apps.pipedrive.tasks.task_sync_pipedrive_models",
        "schedule": crontab(minute=0, hour=0),  # every day at midnight
    },
}
'''

app.conf.beat_schedule = {
    "get-fees-data": {
        "task": "apps.hostify.tasks.task_get_fees_data",
        "schedule": 60 * 60,  # 60 minutes
    },
    "fetch-exchange-rates-every-hour": {
        "task": "apps.properties.tasks.fetch_exchange_rates_task",
        "schedule": 60 * 60,  #  1 hour
    },
}

app.conf.timezone = "UTC"

app.control.rate_limit("apps.hostify.tasks.task_sync_property_with_hostify", "5/m")
