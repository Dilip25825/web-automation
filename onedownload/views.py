from types import SimpleNamespace

from django.core import signing
from django.core.cache import cache
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .drive_catalog import catalog as drive_catalog
from .drive_catalog import download_file, file_is_in_downloads_root, refresh_catalog
from .models import DownloadCatalogSnapshot

SNAPSHOT_CACHE_KEY = 'downloads-saved-catalog-snapshot-v1'


def _resource_icon(*values):
    text = ' '.join(str(value or '') for value in values).lower()
    mappings = [
        (('prerequisites pack', 'automation prerequisites'), 'fa-solid fa-gears', 'bg-violet-100 text-violet-700'),
        (('chromedriver', 'chrome driver'), 'fa-brands fa-chrome', 'bg-amber-100 text-amber-700'),
        (('.net', 'net35', 'framework'), 'fa-solid fa-code', 'bg-violet-100 text-violet-700'),
        (('pdf to excel',), 'fa-solid fa-file-export', 'bg-rose-100 text-rose-700'),
        (('excel', 'xlsx', 'spreadsheet'), 'fa-solid fa-file-excel', 'bg-emerald-100 text-emerald-700'),
        (('pmfby', 'fasal bima'), 'fa-solid fa-wheat-awn', 'bg-green-100 text-green-700'),
        (('jpg', 'jpeg', 'image'), 'fa-solid fa-file-image', 'bg-pink-100 text-pink-700'),
        (('access database', 'database engine'), 'fa-solid fa-database', 'bg-red-100 text-red-700'),
        (('ms office', 'microsoft office'), 'fa-brands fa-microsoft', 'bg-orange-100 text-orange-700'),
        (('erp',), 'fa-solid fa-building-columns', 'bg-blue-100 text-blue-700'),
        (('krp', 'fasal rin', 'loan application'), 'fa-solid fa-hand-holding-dollar', 'bg-indigo-100 text-indigo-700'),
        (('interest',), 'fa-solid fa-percent', 'bg-cyan-100 text-cyan-700'),
        (('uparjan', 'loanentry'), 'fa-solid fa-tractor', 'bg-lime-100 text-lime-700'),
        (('ppacs', 'pacs'), 'fa-solid fa-landmark', 'bg-sky-100 text-sky-700'),
        (('approval', 'approvel'), 'fa-solid fa-circle-check', 'bg-teal-100 text-teal-700'),
        (('driver', 'connector'), 'fa-solid fa-plug', 'bg-yellow-100 text-yellow-700'),
        (('zip', 'archive'), 'fa-solid fa-file-zipper', 'bg-purple-100 text-purple-700'),
        (('utility', 'tool'), 'fa-solid fa-screwdriver-wrench', 'bg-slate-100 text-slate-700'),
    ]
    for keywords, icon_class, colour_class in mappings:
        if any(keyword in text for keyword in keywords):
            return icon_class, colour_class
    return 'fa-solid fa-cloud-arrow-down', 'bg-indigo-100 text-indigo-700'


def _human_file_size(size):
    value = float(size or 0)
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if value < 1024 or unit == 'TB':
            return f'{value:.0f} {unit}' if unit == 'B' else f'{value:.1f} {unit}'
        value /= 1024


def _drive_resources(drive_data):
    category_map = {}
    categories = []
    for drive_category in drive_data['categories']:
        name = drive_category['name']
        filter_id = f"drive-{drive_category['id']}"
        icon_class, icon_colour_class = _resource_icon(name)
        category = SimpleNamespace(
            filter_id=filter_id,
            name=name,
            icon_class=icon_class,
            icon_colour_class=icon_colour_class,
        )
        categories.append(category)
        category_map[name.casefold()] = category

    links = []
    for drive_file in drive_data['files']:
        category_name = drive_file['category_name']
        category = category_map.get(category_name.casefold())
        if category is None:
            filter_id = f"drive-{drive_file['parent_id']}"
            icon_class, icon_colour_class = _resource_icon(category_name)
            category = SimpleNamespace(
                filter_id=filter_id,
                name=category_name,
                icon_class=icon_class,
                icon_colour_class=icon_colour_class,
            )
            categories.append(category)
            category_map[category_name.casefold()] = category


        icon_class, icon_colour_class = _resource_icon(
            drive_file['name'], category_name, drive_file['mime_type'])
        links.append(SimpleNamespace(
            name=drive_file['name'],
            description=f"Google Drive • {_human_file_size(drive_file['size'])}",
            category_name=category_name,
            filter_category_id=category.filter_id,
            drive_link=f"https://drive.google.com/open?id={drive_file['id']}&usp=drive_fs",
            icon_class=icon_class,
            icon_colour_class=icon_colour_class,
        ))

    categories.sort(key=lambda item: item.name.casefold())
    links.sort(key=lambda item: (item.category_name.casefold(), item.name.casefold()))
    return links, categories


def _saved_snapshot():
    snapshot_data = cache.get(SNAPSHOT_CACHE_KEY)
    if snapshot_data is not None:
        return snapshot_data
    snapshot = DownloadCatalogSnapshot.objects.filter(singleton_key=1).first()
    snapshot_data = {
        'catalog': snapshot.catalog if snapshot and isinstance(snapshot.catalog, dict) else {
            'categories': [],
            'files': [],
        },
        'synced_at': snapshot.synced_at if snapshot else None,
        'file_count': snapshot.file_count if snapshot else 0,
        'category_count': snapshot.category_count if snapshot else 0,
    }
    cache.set(SNAPSHOT_CACHE_KEY, snapshot_data, None)
    return snapshot_data


def public_downloads(request):
    snapshot = _saved_snapshot()
    drive_data = snapshot['catalog']
    try:
        links, categories = _drive_resources(drive_data)
        drive_error = ''
    except Exception:
        links, categories = [], []
        drive_error = 'Saved download list load nahi ho saki. Superuser Drive Sync dobara chalayein.'
    return render(request, 'onedownload/public_list.html', {
        'links': links,
        'categories': categories,
        'drive_error': drive_error,
        'download_snapshot': snapshot,
    })


@require_POST
def sync_drive_catalog(request):
    if not request.user.is_authenticated or not request.user.is_superuser:
        return JsonResponse({
            'success': False,
            'message': 'Only superuser can sync Google Drive files.',
        }, status=403)
    try:
        drive_data = refresh_catalog()
        if not isinstance(drive_data, dict):
            raise ValueError('Drive catalog response is invalid.')
        categories = drive_data.get('categories')
        files = drive_data.get('files')
        if not isinstance(categories, list) or not isinstance(files, list):
            raise ValueError('Drive catalog categories or files are invalid.')
        synced_at = timezone.now()
        with transaction.atomic():
            snapshot, _ = DownloadCatalogSnapshot.objects.update_or_create(
                singleton_key=1,
                defaults={
                    'catalog': drive_data,
                    'file_count': len(files),
                    'category_count': len(categories),
                    'synced_at': synced_at,
                    'synced_by': request.user,
                },
            )
        cache.set(SNAPSHOT_CACHE_KEY, {
            'catalog': drive_data,
            'synced_at': snapshot.synced_at,
            'file_count': snapshot.file_count,
            'category_count': snapshot.category_count,
        }, None)
        return JsonResponse({
            'success': True,
            'message': f'{snapshot.file_count} Drive files successfully synced.',
            'file_count': snapshot.file_count,
            'category_count': snapshot.category_count,
        })
    except Exception:
        return JsonResponse({
            'success': False,
            'message': 'Google Drive sync nahi ho saka. Purani download list safe rakhi gayi hai.',
        }, status=503)


@require_GET
def file_download(request, file_id):
    drive_file = next(
        (item for item in drive_catalog()['files'] if item['id'] == file_id),
        None,
    )
    if drive_file is None:
        raise Http404('Download file not found.')
    try:
        response = FileResponse(
            download_file(file_id),
            as_attachment=True,
            filename=drive_file['name'],
            content_type=drive_file['mime_type'],
        )
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
    except Exception:
        return HttpResponse(
            'Download abhi available nahi hai. Kripya kuch der baad dobara try karein.',
            status=503,
            content_type='text/plain; charset=utf-8',
        )


@require_GET
def drive_download(request, token):
    try:
        payload = signing.loads(token, salt='onedownload.drive-file.v1')
        file_id = str(payload.get('file_id') or '').strip()
        filename = str(payload.get('name') or 'download').replace('\r', '').replace('\n', '')
        mime_type = str(payload.get('mime_type') or 'application/octet-stream')
        if not file_id or not file_is_in_downloads_root(file_id):
            raise Http404('Download file not found.')
        response = FileResponse(
            download_file(file_id),
            as_attachment=True,
            filename=filename,
            content_type=mime_type,
        )
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
    except signing.BadSignature as error:
        raise Http404('Invalid download link.') from error
    except Http404:
        raise
    except Exception:
        return HttpResponse(
            'Download abhi available nahi hai. Kripya kuch der baad dobara try karein.',
            status=503,
            content_type='text/plain; charset=utf-8',
        )