import os
import django
from django.core.asgi import get_asgi_application

# Settings module set karein
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator
import apps.delivery.routing  # Hamara routing file import karein

application = ProtocolTypeRouter({
    # 1. HTTP Requests (Standard Django Views)
    "http": get_asgi_application(),

    # 2. WebSocket Requests (Real-time)
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(
                apps.delivery.routing.websocket_urlpatterns
            )
        )
    ),
})



import os
import django
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from apps.accounts.middleware import JwtAuthMiddleware  # <-- Hamara naya middleware import
import apps.delivery.routing

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    
    "websocket": AllowedHostsOriginValidator(
        # AuthMiddlewareStack hata kar hum apna Custom Middleware laga rahe hain
        JwtAuthMiddleware(
            URLRouter(
                apps.delivery.routing.websocket_urlpatterns
            )
        )
    ),
})