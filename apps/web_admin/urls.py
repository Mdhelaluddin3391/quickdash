from django.urls import path
from .views import AdminLoginView, AdminDashboardView

urlpatterns = [
    # Changed name='admin-login' to name='staff-login' to match the template
    path('login/', AdminLoginView.as_view(), name='staff-login'),
    path('', AdminDashboardView.as_view(), name='admin-dashboard'),
]