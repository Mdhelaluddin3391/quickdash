# apps/warehouse/middleware.py
import hashlib, json
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponse
from .models import IdempotencyKey
from django.utils import timezone
from django.conf import settings

IDEMPOTENCY_HEADER = 'HTTP_IDEMPOTENCY_KEY'  # client sends Idempotency-Key header

class IdempotencyMiddleware(MiddlewareMixin):
    """
    For POST endpoints: if client sends Idempotency-Key header, we check DB for previous result.
    If exists and not expired, return saved response. Otherwise let request flow and save response.
    Note: This middleware expects view to set response `X-STORE-IDEMPOTENCY` header to '1' to store.
    Alternative: use decorator to store immediately after view.
    """

    def process_request(self, request):
        if request.method != 'POST':
            return None
        key = request.META.get(IDEMPOTENCY_HEADER)
        if not key:
            return None
        # compute request hash for robustness
        try:
            body = request.body or b''
            h = hashlib.sha256(body).hexdigest()
        except Exception:
            h = ''
        try:
            rec = IdempotencyKey.objects.filter(key=key).first()
            if rec and not rec.is_expired():
                # return cached response
                if rec.response_body is not None and rec.response_status is not None:
                    return HttpResponse(json.dumps(rec.response_body), status=rec.response_status, content_type='application/json')
        except Exception:
            pass
        # attach idempotency info to request for view to store result later
        request._idempotency_key = key
        request._idempotency_request_hash = h
        return None

    def process_response(self, request, response):
        # If request had idempotency and view asked to store, persist
        key = getattr(request, '_idempotency_key', None)
        if not key:
            return response
        try:
            # only store if response ok (2xx or 202 etc) and response instructs store via header
            store = response.get('X-STORE-IDEMPOTENCY', '0') == '1'
            if store:
                body = response.content.decode('utf-8')
                try:
                    body_json = json.loads(body)
                except Exception:
                    body_json = {"body": body}
                rec, created = IdempotencyKey.objects.update_or_create(
                    key=key,
                    defaults={
                        'route': request.path,
                        'request_hash': getattr(request, '_idempotency_request_hash', ''),
                        'response_status': response.status_code,
                        'response_body': body_json,
                        'expires_at': timezone.now() + getattr(settings, 'IDEMPOTENCY_KEY_TTL', timezone.timedelta(minutes=30))
                    }
                )
                # no further action
        except Exception:
            pass
        return response
