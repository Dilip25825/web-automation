"""Temporary compatibility gateway for desktop clients using a retired API host."""

from urllib.parse import urlsplit

import requests
from django.conf import settings
from django.http import HttpResponse, HttpResponseNotAllowed, JsonResponse


_FORWARDED_REQUEST_HEADERS = (
    'Accept',
    'Authorization',
    'Content-Type',
    'X-License-API-Key',
)
_FORWARDED_RESPONSE_HEADERS = (
    'Cache-Control',
    'Content-Disposition',
    'Content-Type',
    'Retry-After',
)
_ALLOWED_METHODS = ('GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS')


def _upstream_url(api_path, query_string):
    base_url = settings.LEGACY_API_GATEWAY_BASE_URL
    parsed = urlsplit(base_url)
    if parsed.scheme != 'https' or not parsed.netloc or parsed.query or parsed.fragment:
        return ''

    url = f'{base_url}/api/licensing/{api_path}'
    if query_string:
        url = f'{url}?{query_string}'
    return url


def proxy_licensing_api(request, api_path):
    """Forward a legacy licensing request without changing its public contract."""
    if request.method not in _ALLOWED_METHODS:
        return HttpResponseNotAllowed(_ALLOWED_METHODS)

    upstream_url = _upstream_url(api_path, request.META.get('QUERY_STRING', ''))
    if not upstream_url:
        return JsonResponse(
            {'success': False, 'status': 'GATEWAY_NOT_CONFIGURED'},
            status=503,
        )

    headers = {
        header: request.headers[header]
        for header in _FORWARDED_REQUEST_HEADERS
        if request.headers.get(header)
    }
    client_ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',', 1)[0].strip()
    if not client_ip:
        client_ip = request.META.get('REMOTE_ADDR', '').strip()
    if client_ip:
        headers['X-Forwarded-For'] = client_ip

    try:
        upstream_response = requests.request(
            method=request.method,
            url=upstream_url,
            data=request.body or None,
            headers=headers,
            timeout=settings.LEGACY_API_GATEWAY_TIMEOUT_SECONDS,
            allow_redirects=False,
        )
    except requests.RequestException:
        return JsonResponse(
            {
                'success': False,
                'status': 'GATEWAY_UPSTREAM_UNAVAILABLE',
                'message': 'Licensing service abhi uplabdh nahi hai. Kripya dobara try karein.',
            },
            status=503,
        )

    response = HttpResponse(upstream_response.content, status=upstream_response.status_code)
    for header in _FORWARDED_RESPONSE_HEADERS:
        value = upstream_response.headers.get(header)
        if value:
            response[header] = value
    return response
