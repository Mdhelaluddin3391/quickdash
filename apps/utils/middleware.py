import time
import logging

logger = logging.getLogger("request_logger")


class RequestLogMiddleware:
    """
    Logs every request + response time + user.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.time()

        response = self.get_response(request)

        duration = time.time() - start
        logger.info(
            "%s %s (status=%s) user=%s duration=%.2fms",
            request.method,
            request.path,
            response.status_code,
            request.user.id if request.user.is_authenticated else "anonymous",
            duration * 1000,
        )

        return response
