from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/warehouse/live/$', consumers.WMSConsumer.as_asgi()),
]