import tempfile
from functools import lru_cache

from django.conf import settings
from django.core.cache import cache
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

FOLDER_MIME_TYPE = 'application/vnd.google-apps.folder'
CACHE_KEY = 'downloads-google-drive-catalog-v1'


def configured():
    return bool(settings.GOOGLE_DRIVE_DOWNLOADS_FOLDER_ID and settings.GOOGLE_SERVICE_ACCOUNT_FILE)


@lru_cache(maxsize=1)
def drive_service():
    credentials = service_account.Credentials.from_service_account_file(
        settings.GOOGLE_SERVICE_ACCOUNT_FILE,
        scopes=['https://www.googleapis.com/auth/drive.readonly'],
    )
    return build('drive', 'v3', credentials=credentials, cache_discovery=False)


def _children(folder_id):
    service = drive_service()
    page_token = None
    while True:
        response = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields='nextPageToken,files(id,name,mimeType,size,createdTime,modifiedTime,parents)',
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            pageSize=1000,
            pageToken=page_token,
        ).execute()
        yield from response.get('files', [])
        page_token = response.get('nextPageToken')
        if not page_token:
            break


def _load_catalog():
    root_id = settings.GOOGLE_DRIVE_DOWNLOADS_FOLDER_ID
    categories = []
    files = []
    pending = [(root_id, '')]
    visited = set()
    while pending:
        folder_id, relative_path = pending.pop(0)
        if folder_id in visited:
            continue
        visited.add(folder_id)
        for item in _children(folder_id):
            if item.get('mimeType') == FOLDER_MIME_TYPE:
                child_path = f"{relative_path} / {item['name']}" if relative_path else item['name']
                categories.append({'id': item['id'], 'name': child_path})
                pending.append((item['id'], child_path))
                continue
            if str(item.get('mimeType') or '').startswith('application/vnd.google-apps.'):
                continue
            category_name = relative_path or 'General'
            files.append({
                'id': item['id'],
                'name': item['name'],
                'mime_type': item.get('mimeType') or 'application/octet-stream',
                'size': int(item.get('size') or 0),
                'created_time': item.get('createdTime') or '',
                'modified_time': item.get('modifiedTime') or '',
                'category_name': category_name,
                'parent_id': folder_id,
            })
    return {'categories': categories, 'files': files}


def catalog():
    if not configured():
        return {'categories': [], 'files': []}
    result = cache.get(CACHE_KEY)
    if result is None:
        result = _load_catalog()
        cache.set(CACHE_KEY, result, settings.GOOGLE_DRIVE_DOWNLOADS_CACHE_SECONDS)
    return result


def refresh_catalog():
    result = _load_catalog()
    cache.set(CACHE_KEY, result, settings.GOOGLE_DRIVE_DOWNLOADS_CACHE_SECONDS)
    return result


def file_is_in_downloads_root(file_id):
    return any(item['id'] == file_id for item in catalog()['files'])

def download_file(file_id):
    output = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode='w+b')
    request = drive_service().files().get_media(fileId=file_id, supportsAllDrives=True)
    downloader = MediaIoBaseDownload(output, request, chunksize=4 * 1024 * 1024)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    output.seek(0)
    return output