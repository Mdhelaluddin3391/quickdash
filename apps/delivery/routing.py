# apps/delivery/routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # ws://domain.com/ws/track/ORDER_123/
    re_path(r'ws/track/(?P<order_id>\w+)/$', consumers.OrderTrackingConsumer.as_asgi()),
]