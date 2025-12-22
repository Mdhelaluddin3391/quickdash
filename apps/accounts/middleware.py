from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from django.core.cache import cache
from urllib.parse import parse_qs

User = get_user_model()

@database_sync_to_async
def get_user_from_id(user_id):
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return AnonymousUser()

class TicketAuthMiddleware:
    """
    Custom Middleware for Channels to authenticate via One-Time Ticket (OTT).
    This replaces standard AuthMiddlewareStack for WebSockets to avoid
    sending tokens in the URL.
    """
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode("utf-8")
        params = parse_qs(query_string)
        ticket = params.get("ticket", [None])[0]

        if ticket:
            cache_key = f"ws_ticket:{ticket}"
            user_id = cache.get(cache_key)

            if user_id:
                # IMMEDIATE INVALIDATION (One-Time Use)
                cache.delete(cache_key)
                scope["user"] = await get_user_from_id(user_id)
            else:
                scope["user"] = AnonymousUser()
        else:
            scope["user"] = AnonymousUser()

        return await self.inner(scope, receive, send)