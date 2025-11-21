from django.urls import path
from .health import health_check
from .views import ServerInfoView

urlpatterns = [
    path("health/", health_check, name="health-check"),
    path("info/", ServerInfoView.as_view(), name="server-info"),
]
