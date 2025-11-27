from django.urls import path
from .views import AdminLoginView, AdminDashboardView

urlpatterns = [
    path('login/', AdminLoginView.as_view(), name='admin-login'),
    path('', AdminDashboardView.as_view(), name='admin-panel'),
]