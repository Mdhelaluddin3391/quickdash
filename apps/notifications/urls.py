# apps/notifications/urls.py
from django.urls import path

from .views import (
    NotificationListView,
    NotificationMarkReadView,
    FCMDeviceRegisterView,
)

urlpatterns = [
    path("", NotificationListView.as_view(), name="notification-list"),
    path("devices/", FCMDeviceRegisterView.as_view(), name="notification-fcm-register"),
    path("<uuid:pk>/read/", NotificationMarkReadView.as_view(), name="notification-mark-read"),
    path("read-all/", NotificationMarkReadView.as_view(), {"pk": "read-all"}, name="notification-mark-all-read"),
]
