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

# Safety limits
MAX_RESPONSE_BYTES = 10_000  # 10KB
ALLOWED_CONTENT_TYPES = {"application/json"}


class IdempotencyMiddleware(MiddlewareMixin):
    """
    Safe production-ready Idempotency middleware.

    - Works for POST only
    - Clients send Idempotency-Key header
    - Middleware returns old response if exists
    - Only stores JSON responses <= 10KB
    - View must set header: X-STORE-IDEMPOTENCY = 1
    """

    def process_request(self, request):
        if request.method != "POST":
            return None

        key = request.META.get(IDEMPOTENCY_HEADER)
        if not key:
            return None

        # Hash request body safely
        try:
            body = request.body or b""
            h = hashlib.sha256(body).hexdigest()
        except Exception:
            logger.exception("Failed to hash request body")
            h = ""

        try:
            rec = IdempotencyKey.objects.filter(key=key).first()
            if rec and not rec.is_expired():
                if rec.response_body is not None and rec.response_status is not None:
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