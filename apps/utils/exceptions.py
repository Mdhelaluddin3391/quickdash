from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)

class BusinessLogicException(Exception):
    """
    Raised when a domain rule is violated (e.g. 'Stock not available').
    """
    def __init__(self, message, code="business_error"):
        self.message = message
        self.code = code
        super().__init__(message)

def custom_exception_handler(exc, context):
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)

    # Handle custom BusinessLogicException
    if isinstance(exc, BusinessLogicException):
        return Response(
            {"error": exc.message, "code": exc.code},
            status=status.HTTP_400_BAD_REQUEST
        )

    # If response is None, it's an unhandled server error (500)
    if response is None:
        logger.error(f"Unhandled Exception: {exc}", exc_info=True)
        return Response(
            {"error": "Internal Server Error", "code": "server_error"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    return response