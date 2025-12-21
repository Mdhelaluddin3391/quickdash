# apps/delivery/routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/rider/location/$", consumers.RiderLocationConsumer.as_asgi()),
    re_path(r"ws/order/track/(?P<order_id>[0-9a-f-]+)/$", consumers.OrderTrackingConsumer.as_asgi()),
]