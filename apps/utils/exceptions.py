from rest_framework.exceptions import APIException


class BadRequest(APIException):
    status_code = 400
    default_detail = "Bad request."


class Unauthorized(APIException):
    status_code = 401
    default_detail = "Unauthorized request."


class Forbidden(APIException):
    status_code = 403
    default_detail = "Access forbidden."


class NotFound(APIException):
    status_code = 404
    default_detail = "Resource not found."


class InternalServerError(APIException):
    status_code = 500
    default_detail = "Internal server error."
