# config/asgi.py
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator

# Import Custom Middleware
from apps.accounts.middleware import TicketAuthMiddleware

# Import routing from apps
from apps.warehouse import websocket as warehouse_routing
from apps.delivery import routing as delivery_routing

websocket_urlpatterns = warehouse_routing.websocket_urlpatterns + delivery_routing.websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AllowedHostsOriginValidator(
        TicketAuthMiddleware(
            URLRouter(
                websocket_urlpatterns
            )
        )
    ),
})