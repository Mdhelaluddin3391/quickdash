from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    RequestOTPView,
    VerifyOTPView,
    MeView,
    LogoutView,
)
from .views_roles import ChangeUserRole 

urlpatterns = [
    path('request-otp/', RequestOTPView.as_view(), name='request-otp'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('me/', MeView.as_view(), name='me'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path("change-role/", ChangeUserRole.as_view()),
]
