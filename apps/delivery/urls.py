from django.urls import path
from .views import (
    UpdateRiderLocationAPIView,
    GetRiderLocationAPIView,
    GetMyCurrentTaskAPIView,
    UpdateTaskStatusAPIView,
)

urlpatterns = [
    # Rider App se location/status update lene ke liye
    # POST /api/v1/delivery/location/update/
    path('location/update/', UpdateRiderLocationAPIView.as_view(), name='update-rider-location'),
    
    # (Optional) Admin ke liye rider ki location dekhne ke liye
    # GET /api/v1/delivery/location/<rider_id>/
    path('location/<uuid:rider__id>/', GetRiderLocationAPIView.as_view(), name='get-rider-location'),
    
    # Rider App ke liye uska current active task fetch karne ke liye
    # GET /api/v1/delivery/task/current/
    path('task/current/', GetMyCurrentTaskAPIView.as_view(), name='get-current-task'),
    
    # Rider App se task ka status update karne ke liye (e.g., picked_up, delivered)
    # POST /api/v1/delivery/task/update_status/
    path('task/update_status/', UpdateTaskStatusAPIView.as_view(), name='update-task-status'),
]