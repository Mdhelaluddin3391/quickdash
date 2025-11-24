import os
import django
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from apps.accounts.middleware import JwtAuthMiddleware
import apps.delivery.routing
import apps.warehouse.routing

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AllowedHostsOriginValidator(
        JwtAuthMiddleware(
            URLRouter(
                apps.delivery.routing.websocket_urlpatterns +
                apps.warehouse.routing.websocket_urlpatterns
            )
        )
    ),
})
