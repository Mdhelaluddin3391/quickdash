from django.urls import path
from .health import health_check
from .views import ServerInfoView
from .views import GlobalConfigView


urlpatterns = [
    path("health/", health_check, name="health-check"),
    path("info/", ServerInfoView.as_view(), name="server-info"),
    path("config/", GlobalConfigView.as_view(), name="global-config"),
    
]
