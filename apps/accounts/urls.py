from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    RequestOTPView,
    VerifyOTPView,
    MeView,
    LogoutView,
    CustomerRequestOTPView,
    CustomerVerifyOTPView,
    CustomerMeView,
    CustomerAddressListCreateView,
    CustomerAddressDetailView,
    SetDefaultAddressView,
)
from .views_social import GoogleLoginView 
from .views_roles import ChangeUserRole
from .views_onboarding import (   # <--- NEW
    RiderApplyView,
    AdminRiderListView,
    AdminApproveRiderView,
    AdminRejectRiderView,
    AdminEmployeeListCreateView,
    AdminEmployeeStatusUpdateView,
)
from .views_roles import ChangeUserRole

urlpatterns = [
    # Generic endpoints (with login_type in body)
    path('request-otp/', RequestOTPView.as_view(), name='request-otp'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),

    # CUSTOMER-specific endpoints (frontends ke liye easy)
    path('customer/request-otp/', CustomerRequestOTPView.as_view(), name='customer-request-otp'),
    path('customer/verify-otp/', CustomerVerifyOTPView.as_view(), name='customer-verify-otp'),
    path('customer/me/', CustomerMeView.as_view(), name='customer-me'),
    path('customer/addresses/', CustomerAddressListCreateView.as_view(), name='customer-address-list-create'),
    path('customer/addresses/<int:pk>/', CustomerAddressDetailView.as_view(), name='customer-address-detail'),
    path('customer/addresses/<int:pk>/set-default/', SetDefaultAddressView.as_view(), name='customer-address-set-default'),

    # Generic user info / logout
    path('me/', MeView.as_view(), name='me'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Admin: change app_role
    path("users/<uuid:user_id>/role/", ChangeUserRole.as_view()),

    path('auth/google/', GoogleLoginView.as_view(), name='google-login'),
]


