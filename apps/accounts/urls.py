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
    AdminLoginView,
    AdminMeView,
    AdminCreateRiderView,
    AdminChangeRiderStatusView,
    AdminCreateEmployeeView,
    AdminChangeEmployeeStatusView,
    AdminForgotPasswordView,
    AdminResetPasswordView,
    CustomTokenRefreshView,
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

    # Admin auth
    path("admin/login/", AdminLoginView.as_view()),
    path("admin/me/", AdminMeView.as_view()),

    path("admin/forgot-password/", AdminForgotPasswordView.as_view()),
    path("admin/reset-password/", AdminResetPasswordView.as_view()),

    # Admin rider/employee management
    path("admin/riders/create/", AdminCreateRiderView.as_view()),
    path("admin/riders/change-status/", AdminChangeRiderStatusView.as_view()),
    path("admin/employees/create/", AdminCreateEmployeeView.as_view()),
    path("admin/employees/change-status/", AdminChangeEmployeeStatusView.as_view()),

    # token refresh
    path("token/refresh/", CustomTokenRefreshView.as_view()),
    # logout
    path("logout/", LogoutView.as_view()),
]
