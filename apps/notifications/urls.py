# apps/notifications/urls.py
from django.urls import path
from .views import NotificationListView, NotificationDetailView, RegisterFCMTokenView, NotificationMarkReadView

urlpatterns = [
    # GET /api/v1/notifications/
    path('', NotificationListView.as_view(), name='notification-list'),
    
    # GET /api/v1/notifications/<id>/
    # POST /api/v1/notifications/<id>/mark_as_read/
    path('<int:pk>/', NotificationDetailView.as_view(), name='notification-detail'),
    path('<int:pk>/mark_as_read/', NotificationMarkReadView.as_view(), name='notification-mark-read'),
    path('register-device/', RegisterFCMTokenView.as_view(), name='register-fcm-device'),
]