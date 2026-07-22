import io
import os
import uuid
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.text import get_valid_filename
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from PIL import Image, UnidentifiedImageError

ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.webp'}
ALLOWED_MIME_TYPES = {'application/pdf', 'image/jpeg', 'image/png', 'image/webp'}

def _configuration():
    folder_id = settings.GOOGLE_DRIVE_FOLDER_ID
    credentials_file = settings.GOOGLE_SERVICE_ACCOUNT_FILE
    if not folder_id or not credentials_file:
        raise RuntimeError('Google Drive attachment configuration is incomplete.')
    return folder_id, credentials_file

@lru_cache(maxsize=1)
def drive_service():
    _, credentials_file = _configuration()
    credentials = service_account.Credentials.from_service_account_file(
        credentials_file, scopes=['https://www.googleapis.com/auth/drive.file'])
    return build('drive', 'v3', credentials=credentials, cache_discovery=False)

def validate_attachment(uploaded_file):
    if not uploaded_file:
        return
    if uploaded_file.size > settings.KHATA_ATTACHMENT_MAX_SIZE:
        raise ValidationError('Attachment ka size 5 MB se adhik nahi ho sakta.')
    extension = Path(uploaded_file.name).suffix.lower()
    mime_type = (uploaded_file.content_type or '').lower()
    if extension not in ALLOWED_EXTENSIONS or mime_type not in ALLOWED_MIME_TYPES:
        raise ValidationError('Sirf PDF, JPG, PNG ya WebP file upload karein.')
    uploaded_file.seek(0)
    if extension == '.pdf':
        if uploaded_file.read(5) != b'%PDF-':
            raise ValidationError('Yeh valid PDF file nahi hai.')
    else:
        try:
            image = Image.open(uploaded_file)
            image.verify()
            expected = {'JPEG'} if extension in {'.jpg', '.jpeg'} else {extension[1:].upper()}
            if image.format not in expected:
                raise ValidationError('Image file ka format uske extension se match nahi karta.')
        except (UnidentifiedImageError, OSError):
            raise ValidationError('Yeh valid image file nahi hai.')
    uploaded_file.seek(0)

def upload_attachment(uploaded_file, transaction):
    validate_attachment(uploaded_file)
    folder_id, _ = _configuration()
    safe_name = get_valid_filename(os.path.basename(uploaded_file.name)) or 'attachment'
    drive_name = f'{uuid.uuid4().hex}_{safe_name}'
    media = MediaIoBaseUpload(uploaded_file.file, mimetype=uploaded_file.content_type, resumable=False)
    result = drive_service().files().create(
        body={'name': drive_name, 'parents': [folder_id], 'appProperties': {
            'khata_transaction_id': str(transaction.id),
            'khata_customer_id': str(transaction.customer_id),
            'khata_user_id': str(transaction.customer.user_id)}},
        media_body=media, fields='id,name,mimeType,size', supportsAllDrives=True).execute()
    return {'attachment_drive_id': result['id'], 'attachment_name': safe_name,
            'attachment_mime_type': result.get('mimeType') or uploaded_file.content_type,
            'attachment_size': int(result.get('size') or uploaded_file.size)}

def delete_attachment(file_id):
    if not file_id:
        return
    try:
        drive_service().files().delete(fileId=file_id, supportsAllDrives=True).execute()
    except HttpError as error:
        if error.resp.status != 404:
            raise

def download_attachment(file_id):
    output = io.BytesIO()
    request = drive_service().files().get_media(fileId=file_id, supportsAllDrives=True)
    downloader = MediaIoBaseDownload(output, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    output.seek(0)
    return output
