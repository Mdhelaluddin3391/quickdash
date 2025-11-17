from django.urls import re_path
from .consumers import WMSConsumer

websocket_urlpatterns = [
    re_path(r"ws/wms/$", WMSConsumer.as_asgi()),
]
