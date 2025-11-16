from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    CustomerRequestOTPView,
    CustomerVerifyOTPView,
    RiderRequestOTPView,
    RiderVerifyOTPView,
    EmployeeRequestOTPView,
    EmployeeVerifyOTPView,
    LogoutView,
    CustomerMeView,
    RiderMeView,
    EmployeeMeView,
)

urlpatterns = [
    # Customer auth
    path("customer/request-otp/", CustomerRequestOTPView.as_view()),
    path("customer/verify-otp/", CustomerVerifyOTPView.as_view()),
    path("customer/me/", CustomerMeView.as_view()),

    # Rider auth
    path("rider/request-otp/", RiderRequestOTPView.as_view()),
    path("rider/verify-otp/", RiderVerifyOTPView.as_view()),
    path("rider/me/", RiderMeView.as_view()),

    # Employee auth
    path("employee/request-otp/", EmployeeRequestOTPView.as_view()),
    path("employee/verify-otp/", EmployeeVerifyOTPView.as_view()),
    path("employee/me/", EmployeeMeView.as_view()),

    # token refresh
    path("token/refresh/", TokenRefreshView.as_view()),
    # logout
    path("logout/", LogoutView.as_view()),
]
