import logging
import json
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse

logger = logging.getLogger("django")

class GlobalExceptionMiddleware(MiddlewareMixin):
    """
    Last line of defense for non-DRF views.
    """
    def process_exception(self, request, exception):
        logger.exception(f"Unhandled Middleware Exception: {str(exception)}")
        if request.path.startswith('/api/'):
            return JsonResponse(
                {"error": "Internal System Error"}, 
                status=500
            )
        return None # Let Django's default 500 handler work for HTML