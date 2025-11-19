from django.urls import path
from .consumers import RiderLocationConsumer

websocket_urlpatterns = [
    # Rider is URL par connect karega: ws://localhost:8000/ws/delivery/tracker/
    path("ws/delivery/tracker/", RiderLocationConsumer.as_asgi()),
]