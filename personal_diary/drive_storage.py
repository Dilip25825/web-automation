"""Private Google Drive storage for diary media; no public Drive links."""
import io
import os
import uuid
from functools import lru_cache

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.text import get_valid_filename
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload


@lru_cache(maxsize=1)
def drive_service():
    if not settings.PERSONAL_DIARY_DRIVE_ROOT_ID or not settings.GOOGLE_SERVICE_ACCOUNT_FILE:
        raise ImproperlyConfigured('Personal Diary Google Drive configuration is incomplete.')
    credentials = service_account.Credentials.from_service_account_file(
        settings.GOOGLE_SERVICE_ACCOUNT_FILE,
        scopes=['https://www.googleapis.com/auth/drive'],
    )
    return build('drive', 'v3', credentials=credentials, cache_discovery=False)


def _folder(name, parent_id):
    service = drive_service()
    query = f"name = '{name.replace("'", "\\'")}' and '{parent_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    found = service.files().list(q=query, fields='files(id)', supportsAllDrives=True, includeItemsFromAllDrives=True).execute().get('files', [])
    if found:
        return found[0]['id']
    return service.files().create(body={'name': name, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [parent_id]}, fields='id', supportsAllDrives=True).execute()['id']


def user_media_folder(user_id, media_type):
    user_folder = _folder(f'user_{user_id}', _folder('users', settings.PERSONAL_DIARY_DRIVE_ROOT_ID))
    return _folder(media_type.lower(), user_folder)


def upload(uploaded_file, user_id, media_type, mime_type=None):
    parent = user_media_folder(user_id, media_type)
    safe_name = get_valid_filename(os.path.basename(uploaded_file.name)) or 'media'
    result = drive_service().files().create(
        body={'name': f'{uuid.uuid4().hex}_{safe_name}', 'parents': [parent]},
        media_body=MediaIoBaseUpload(uploaded_file.file, mimetype=mime_type or uploaded_file.content_type, resumable=True),
        fields='id,mimeType,size', supportsAllDrives=True,
    ).execute()
    return result, parent, safe_name


def download(file_id):
    output = io.BytesIO()
    downloader = MediaIoBaseDownload(output, drive_service().files().get_media(fileId=file_id, supportsAllDrives=True))
    done = False
    while not done:
        _, done = downloader.next_chunk()
    output.seek(0)
    return output


def delete(file_id):
    """Permanently remove a Drive object only after its DB record is eligible for cleanup."""
    drive_service().files().delete(fileId=file_id, supportsAllDrives=True).execute()
