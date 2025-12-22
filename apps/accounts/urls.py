from django.urls import path
from .views import SendOTPView, LoginWithOTPView, MeView, CreateWsTicketView
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('otp/send/', SendOTPView.as_view(), name='otp-send'),
    path('otp/login/', LoginWithOTPView.as_view(), name='otp-login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('me/', MeView.as_view(), name='user-me'),
    path('ws/ticket/', CreateWsTicketView.as_view(), name='ws-ticket'),
]