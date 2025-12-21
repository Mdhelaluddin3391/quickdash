import time
import logging
from django.conf import settings

logger = logging.getLogger("request_logger")

class RequestLogMiddleware:
    """
    Logs request duration.
    PRODUCTION FIX: Only logs requests that are slow (>1s) or errors (>=400) 
    to prevent I/O blocking and log spam.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.time()
        response = self.get_response(request)
        duration = time.time() - start

        # Logic: Log if DEBUG is True OR if request was slow/error
        is_slow = duration > 1.0  # 1 second threshold
        is_error = response.status_code >= 400

        if settings.DEBUG or is_slow or is_error:
            user_id = request.user.id if request.user.is_authenticated else "anonymous"
            log_level = logging.ERROR if is_error else logging.INFO
            
            logger.log(
                log_level,
                "%s %s (status=%s) user=%s duration=%.2fms",
                request.method,
                request.path,
                response.status_code,
                user_id,
                duration * 1000,
            )

        return response