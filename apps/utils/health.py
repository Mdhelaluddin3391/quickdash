from django.http import JsonResponse
from django.db import connection
from django_redis import get_redis_connection

def health_check(request):
    status = {"db": "unknown", "redis": "unknown"}
    try:
        # Check DB
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        status["db"] = "ok"
        
        # Check Redis
        conn = get_redis_connection("default")
        conn.ping()
        status["redis"] = "ok"

        return JsonResponse({"status": "ok", "components": status}, status=200)
    except Exception as e:
        return JsonResponse(
            {"status": "error", "detail": str(e), "components": status}, 
            status=503
        )