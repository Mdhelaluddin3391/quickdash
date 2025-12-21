import hashlib
import json
import logging
from datetime import timedelta
from django.core.cache import cache
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse, HttpResponseBadRequest
from django.utils import timezone
from django.conf import settings
from .models import IdempotencyKey

logger = logging.getLogger(__name__)

IDEMPOTENCY_HEADER = "HTTP_IDEMPOTENCY_KEY"
MAX_REQUEST_BODY_SIZE = 2 * 1024 * 1024  # 2MB Limit for Idempotency
ALLOWED_CONTENT_TYPES = {"application/json"}
LOCK_TIMEOUT = 60  # Increased for production safety (DB latency buffer)

class IdempotencyMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.method not in ('POST', 'PATCH'):
            return None

        key = request.META.get(IDEMPOTENCY_HEADER)
        if not key:
            return None

        # 1. DoS Protection: Skip if body is too large
        if int(request.META.get('CONTENT_LENGTH', 0)) > MAX_REQUEST_BODY_SIZE:
             logger.warning("Idempotency: Request body too large, skipping.")
             return None

        # SKIP if this is a file upload (multipart) to prevent memory issues
        if request.content_type.startswith("multipart/form-data"):
            return None

        # 2. Concurrency Lock (Redis) - PREVENTS RACE CONDITIONS
        lock_key = f"idemp_lock:{key}"
        # Store a unique identifier for this specific request thread (Timestamp is sufficient for unique-per-request context)
        request_id = str(timezone.now().timestamp())

        if not cache.add(lock_key, request_id, timeout=LOCK_TIMEOUT):
            return JsonResponse(
                {"detail": "Request is currently being processed. Please wait."},
                status=409 # Conflict
            )

        # 3. Check DB for Completed Response
        try:
            # Safe access to body
            body = request.body or b""
            h = hashlib.sha256(body).hexdigest()
        except Exception:
            logger.warning("Idempotency: Could not read request body.")
            return HttpResponseBadRequest("Invalid request body")

        try:
            rec = IdempotencyKey.objects.filter(key=key).first()
            if rec and not rec.is_expired():
                # Release lock immediately if we have a cached response
                # (We own the lock we just set, so we can delete it safely)
                cache.delete(lock_key)

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
        request._idempotency_lock_key = lock_key
        request._idempotency_req_id = request_id  # Track this ID for safe release
        return None

    def process_response(self, request, response):
        key = getattr(request, "_idempotency_key", None)
        lock_key = getattr(request, "_idempotency_lock_key", None)
        req_id = getattr(request, "_idempotency_req_id", None)
        
        # FIX: Only release the lock if WE own it
        # This prevents deleting a lock that might have been re-acquired by a retry
        # if this request took longer than LOCK_TIMEOUT.
        if lock_key and req_id:
            current_lock = cache.get(lock_key)
            if current_lock == req_id:
                cache.delete(lock_key)

        if not key:
            return response

        # Only cache successful/client-error responses (2xx, 4xx)
        # Avoid caching 500s usually
        if not (200 <= response.status_code < 500):
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
            if len(body_bytes) > MAX_REQUEST_BODY_SIZE:
                logger.warning("Idempotency: Skipping store (body too large)")
                return response

            # Parse JSON safely
            try:
                body_json = json.loads(body_bytes.decode("utf-8", errors="ignore"))
            except Exception:
                body_json = {"body": body_bytes.decode("utf-8", errors="ignore")}

            ttl = getattr(settings, "IDEMPOTENCY_KEY_TTL", 300)
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