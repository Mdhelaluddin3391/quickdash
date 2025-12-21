from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from urllib.parse import parse_qs

User = get_user_model()

@database_sync_to_async
def get_user(token_key):
    """
    Database se user fetch karne ke liye async helper.
    """
    try:
        # SimpleJWT se token decode karein
        access_token = AccessToken(token_key)
        user_id = access_token['user_id']
        return User.objects.get(id=user_id)
    except (InvalidToken, TokenError, User.DoesNotExist):
        return AnonymousUser()

class JwtAuthMiddleware:
    """
    Custom Middleware jo Query Params (?token=...) se JWT nikal kar
    User authenticate karta hai.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # 1. Query String Parse karein
        query_string = scope.get("query_string", b"").decode("utf-8")
        query_params = parse_qs(query_string)
        
        # 2. 'token' parameter dhundhe
        token = query_params.get("token", [None])[0]

        # 3. Agar token hai toh user verify karein
        if token:
            scope["user"] = await get_user(token)
        else:
            scope["user"] = AnonymousUser()

        return await self.app(scope, receive, send)