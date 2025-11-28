import hashlib
import json
import logging
from datetime import timedelta
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from django.utils import timezone
from django.conf import settings
from .models import IdempotencyKey

logger = logging.getLogger(__name__)

IDEMPOTENCY_HEADER = "HTTP_IDEMPOTENCY_KEY"
MAX_RESPONSE_BYTES = 1024 * 1024  
ALLOWED_CONTENT_TYPES = {"application/json"}


class IdempotencyMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.method not in ('POST', 'PATCH'):
            return None

        key = request.META.get(IDEMPOTENCY_HEADER)
        if not key:
            return None

        # SKIP if this is a file upload (multipart) to prevent memory issues
        if request.content_type.startswith("multipart/form-data"):
            return None

        try:
            # Safe access to body
            body = request.body or b""
            h = hashlib.sha256(body).hexdigest()
        except Exception:
            logger.warning("Idempotency: Could not read request body, skipping.")
            return None

        try:
            rec = IdempotencyKey.objects.filter(key=key).first()
            if rec and not rec.is_expired():
                # Hash check ensures we don't return cached response for a DIFFERENT body with same key
                if rec.request_hash == h and rec.response_body is not None:
                    return JsonResponse(
                        rec.response_body,
                        status=rec.response_status,
                        safe=isinstance(rec.response_body, dict),
                    )
        except Exception:
            logger.exception("Failed checking idempotency key")

        request._idempotency_key = key
        request._idempotency_request_hash = h
        return None

    def process_response(self, request, response):
        key = getattr(request, "_idempotency_key", None)
        if not key:
            return response

        try:
            should_store = response.get("X-STORE-IDEMPOTENCY", "0") == "1"
            if not should_store:
                return response

            # Check content type
            content_type = response.get("Content-Type", "").split(";")[0].strip()
            if content_type not in ALLOWED_CONTENT_TYPES:
                logger.warning("Idempotency: Skipping store (content-type unsafe)")
                return response

            # Grab safe body
            body_bytes = getattr(response, "content", b"") or b""

            # Limit size
            if len(body_bytes) > MAX_RESPONSE_BYTES:
                logger.warning("Idempotency: Skipping store (body too large)")
                return response

            # Parse JSON safely
            try:
                body_json = json.loads(body_bytes.decode("utf-8", errors="ignore"))
            except Exception:
                body_json = {"body": body_bytes.decode("utf-8", errors="ignore")}

            ttl = getattr(settings, "IDEMPOTENCY_KEY_TTL", 30)
            expires_at = timezone.now() + timedelta(minutes=ttl)

            IdempotencyKey.objects.update_or_create(
                key=key,
                defaults={
                    "route": request.path,
                    "request_hash": getattr(
                        request, "_idempotency_request_hash", ""
                    ),
                    "response_status": response.status_code,
                    "response_body": body_json,
                    "expires_at": expires_at,
                },
            )

        except Exception:
            logger.exception("Error storing idempotency data")

        return response