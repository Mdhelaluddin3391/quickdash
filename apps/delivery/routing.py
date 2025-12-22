from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/delivery/(?P<job_id>[0-9a-f-]+)/$', consumers.DeliveryConsumer.as_asgi()),
]