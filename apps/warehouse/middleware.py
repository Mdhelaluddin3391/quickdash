# apps/warehouse/middleware.py
import hashlib
import json
import logging
from datetime import timedelta

from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponse
from django.utils import timezone
from django.conf import settings

from .models import IdempotencyKey

logger = logging.getLogger(__name__)

IDEMPOTENCY_HEADER = "HTTP_IDEMPOTENCY_KEY"


class IdempotencyMiddleware(MiddlewareMixin):
    """
    For POST endpoints: if client sends Idempotency-Key header, we check DB for previous result.
    If exists and not expired, return saved response.
    View must set response header 'X-STORE-IDEMPOTENCY' = '1' to store.
    """

    def process_request(self, request):
        if request.method != "POST":
            return None
        key = request.META.get(IDEMPOTENCY_HEADER)
        if not key:
            return None

        try:
            body = request.body or b""
            h = hashlib.sha256(body).hexdigest()
        except Exception:
            logger.exception("Failed to hash request body for idempotency")
            h = ""

        try:
            rec = IdempotencyKey.objects.filter(key=key).first()
            if rec and not rec.is_expired():
                if rec.response_body is not None and rec.response_status is not None:
                    return HttpResponse(
                        json.dumps(rec.response_body),
                        status=rec.response_status,
                        content_type="application/json",
                    )
        except Exception:
            logger.exception("Error checking idempotency key %s", key)

        request._idempotency_key = key
        request._idempotency_request_hash = h
        return None

    def process_response(self, request, response):
        key = getattr(request, "_idempotency_key", None)
        if not key:
            return response

        try:
            store = response.get("X-STORE-IDEMPOTENCY", "0") == "1"
            if store:
                body = response.content.decode("utf-8")
                try:
                    body_json = json.loads(body)
                except Exception:
                    body_json = {"body": body}

                ttl = getattr(settings, "IDEMPOTENCY_KEY_TTL", 30)  # minutes
                expires_at = timezone.now() + timedelta(minutes=ttl)

                IdempotencyKey.objects.update_or_create(
                    key=key,
                    defaults={
                        "route": request.path,
                        "request_hash": getattr(request, "_idempotency_request_hash", ""),
                        "response_status": response.status_code,
                        "response_body": body_json,
                        "expires_at": expires_at,
                    },
                )
        except Exception:
            logger.exception("Error storing idempotency key %s", key)
        return response
