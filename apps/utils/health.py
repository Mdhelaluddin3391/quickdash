from django.http import JsonResponse
from django.db import connection


def health_check(request):
    try:
        connection.cursor()
        return JsonResponse({"status": "ok"}, status=200)
    except Exception as e:
        return JsonResponse({"status": "error", "detail": str(e)}, status=500)
