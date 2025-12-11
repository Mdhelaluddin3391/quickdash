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
    LocationServiceCheckView,
)
from .views_social import GoogleLoginView
from .views_roles import ChangeUserRole
from .views_onboarding import (
    RiderApplyView,
    AdminRiderListView,
    AdminApproveRiderView,
    AdminRejectRiderView,
    AdminEmployeeListCreateView,
    AdminEmployeeStatusUpdateView,
)

from django.urls import path
from .views import SendOTPView, LoginWithOTPView, StaffGoogleLoginView
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    # Generic endpoints
    path('request-otp/', RequestOTPView.as_view(), name='request-otp'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),

    # Customer-friendly
    path('customer/request-otp/', CustomerRequestOTPView.as_view(), name='customer-request-otp'),
    path('customer/verify-otp/', CustomerVerifyOTPView.as_view(), name='customer-verify-otp'),
    path('customer/me/', CustomerMeView.as_view(), name='customer-me'),
    path('customer/addresses/', CustomerAddressListCreateView.as_view(), name='customer-address-list-create'),
    path('customer/addresses/<int:pk>/', CustomerAddressDetailView.as_view(), name='customer-address-detail'),
    path('customer/addresses/<int:pk>/set-default/', SetDefaultAddressView.as_view(), name='customer-address-set-default'),

    # Generic user info / logout / token refresh
    path('me/', MeView.as_view(), name='me'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Admin: change app_role
    path("users/<uuid:user_id>/role/", ChangeUserRole.as_view()),

    # Social / Google login for admin
    path('auth/google/', GoogleLoginView.as_view(), name='google-login'),

    # Onboarding / admin endpoints
    path('onboarding/rider/apply/', RiderApplyView.as_view(), name='rider-apply'),
    path('admin/riders/', AdminRiderListView.as_view(), name='admin-rider-list'),
    path('admin/riders/<uuid:pk>/approve/', AdminApproveRiderView.as_view(), name='admin-approve-rider'),
    path('admin/riders/<uuid:pk>/reject/', AdminRejectRiderView.as_view(), name='admin-reject-rider'),

    path('admin/employees/', AdminEmployeeListCreateView.as_view(), name='admin-employee-list-create'),
    path('admin/employees/<uuid:pk>/status/', AdminEmployeeStatusUpdateView.as_view(), name='admin-employee-status-update'),

    # location service page
    path('location/service-check/', LocationServiceCheckView.as_view(), name='location-service-check'),

    # Mobile App / Web Consumer Auth
    path('auth/otp/send/', SendOTPView.as_view(), name='send-otp'),
    path('auth/otp/login/', LoginWithOTPView.as_view(), name='login-otp'),
    
    # Admin Panel Staff Auth
    path('auth/google/login/', StaffGoogleLoginView.as_view(), name='google-login'),
    
    # Token Management
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
