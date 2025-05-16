import datetime
import io
import uuid

from django.conf import settings
from django.utils import timezone
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload


class GoogleApiBase:
    credentials = None
    service = None
    service_name = None
    service_version = None

    def __init__(self):
        self.credentials = self.get_google_api_credentials()
        self.service = self.get_google_api_service()

    @staticmethod
    def get_google_api_credentials():
        credentials = service_account.Credentials.from_service_account_file(
            settings.GOOGLE_SECRET_FILE, scopes=settings.GOOGLE_SCOPES
        )
        return credentials

    def get_google_api_service(self):
        service = build(
            self.get_service_name(),
            self.get_service_version(),
            credentials=self.credentials,
        )
        return service

    def get_service_name(self):
        if self.service_name is None:
            raise NotImplementedError("service_name must be defined")
        return self.service_name

    def get_service_version(self):
        if self.service_version is None:
            raise NotImplementedError("service_version must be defined")
        return self.service_version


class GoogleDriveApi(GoogleApiBase):
    service_name = "drive"
    service_version = "v3"

    def get_google_drive_files(self):
        results = self.service.files().list(pageSize=10, fields="nextPageToken, files(id, name, webViewLink)").execute()
        return results.get("files", [])

    def get_google_drive_changes(self):
        start_page_token = self.service.changes().getStartPageToken().execute()
        token = int(start_page_token.get("startPageToken")) - 1
        changes = self.service.changes().list(pageToken=token).execute()
        return changes.get("changes", [])

    def register_google_webhook(self):
        channel_id = str(uuid.uuid4())
        expiration = timezone.now() + timezone.timedelta(hours=1)
        expiry_unix = int(datetime.datetime.timestamp(expiration) * 1000)
        body = {
            "id": channel_id,
            "type": "web_hook",
            "address": settings.NOTIFICATION_URL,
            "token": expiration.strftime("%Y-%m-%dT%H:%M:%S"),
            "expiration": expiry_unix,  # convert to unix time in milliseconds
            "resourceId": settings.UPDATE_FILE_ID,
        }
        start_page_token = self.service.changes().getStartPageToken().execute()
        self.service.changes().watch(body=body, pageToken=start_page_token).execute()

    def get_google_drive_images(self, folder_id):
        q = f"'{folder_id}' in parents"
        response = self.service.files().list(q=q).execute()
        return response.get("files", [])

    def download_google_drive_image(self, file_id):
        request = self.service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
        return fh.getvalue()

    def get_google_sheet_file(self, file_id):
        result = self.service.files().export(fileId=file_id, mimeType="text/tab-separated-values").execute()
        return result.decode("utf-8").split("\r\n")


class GoogleSheetsAPI(GoogleApiBase):
    service_name = "sheets"
    service_version = "v4"

    def update_google_sheet_file(self, range_name, values, spreadsheet_id=settings.UPDATE_FILE_ID):
        body = {"values": values}
        result = (
            self.service.spreadsheets()
            .values()
            .update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption="USER_ENTERED",
                body=body,
            )
            .execute()
        )
        return result
