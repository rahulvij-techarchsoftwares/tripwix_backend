import pytest


@pytest.fixture(autouse=True)
def mock_google_celery(mocker):
    mocker.patch("apps.properties.tasks.fetch_images_from_google_drive.apply_async")
    mocker.patch("apps.properties.tasks.fetch_multiple_images_from_google_drive.apply_async")
    mocker.patch("apps.properties.tasks.refresh_google_webhook.apply_async")
