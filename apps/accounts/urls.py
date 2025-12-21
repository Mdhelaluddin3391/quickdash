from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    # Auth Views
    SendOTPView,
    LoginWithOTPView,
    StaffGoogleLoginView,
    LogoutView,
    
    # Profile Views
    MeView,
    CustomerMeView,
    CustomerAddressListCreateView,
    CustomerAddressDetailView,
    SetDefaultAddressView,
    
    # Misc
    LocationServiceCheckView
)

from .views_social import GoogleLoginView # Optional: if you kept the old general google login for some reason, otherwise remove
from .views_roles import ChangeUserRole
from .views_onboarding import (
    RiderApplyView,
    AdminRiderListView,
    AdminApproveRiderView,
    AdminRejectRiderView,
    AdminEmployeeListCreateView,
    AdminEmployeeStatusUpdateView,
)
from .views_location import CheckServiceabilityView, SaveCurrentLocationView
from apps.delivery.views_api import UpdateRiderLocationView



urlpatterns = [
    # ==========================
    # AUTHENTICATION
    # ==========================
    # Mobile/Web Consumer & Rider/Employee Login
    path('auth/otp/send/', SendOTPView.as_view(), name='send-otp'),
    path('auth/otp/login/', LoginWithOTPView.as_view(), name='login-otp'),
    
    # Admin Panel Staff Login (Google)
    path('auth/google/login/', StaffGoogleLoginView.as_view(), name='staff-google-login'),
    
    # Token & Logout
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),

    # ==========================
    # PROFILES & USER INFO
    # ==========================
    path('me/', MeView.as_view(), name='me'),
    
    # Customer Specific
    path('customer/me/', CustomerMeView.as_view(), name='customer-me'),
    path('customer/addresses/', CustomerAddressListCreateView.as_view(), name='customer-address-list-create'),
    path('customer/addresses/<int:pk>/', CustomerAddressDetailView.as_view(), name='customer-address-detail'),
    path('customer/addresses/<int:pk>/set-default/', SetDefaultAddressView.as_view(), name='customer-address-set-default'),

    # ==========================
    # ADMIN / ONBOARDING
    # ==========================
    path("users/<uuid:user_id>/role/", ChangeUserRole.as_view()),
    
    # Rider Onboarding
    path('onboarding/rider/apply/', RiderApplyView.as_view(), name='rider-apply'),
    path('admin/riders/', AdminRiderListView.as_view(), name='admin-rider-list'),
    path('admin/riders/<uuid:pk>/approve/', AdminApproveRiderView.as_view(), name='admin-approve-rider'),
    path('admin/riders/<uuid:pk>/reject/', AdminRejectRiderView.as_view(), name='admin-reject-rider'),

    # Employee Management
    path('admin/employees/', AdminEmployeeListCreateView.as_view(), name='admin-employee-list-create'),
    path('admin/employees/<uuid:pk>/status/', AdminEmployeeStatusUpdateView.as_view(), name='admin-employee-status-update'),

    # Misc
    path('location/service-check/', LocationServiceCheckView.as_view(), name='location-service-check'),

    path('location/check-serviceability/', CheckServiceabilityView.as_view(), name='check-serviceability'),
    path('location/save-current/', SaveCurrentLocationView.as_view(), name='save-current-location'),
    
    # RIDER ROUTES
    path('delivery/rider/update-location/', UpdateRiderLocationView.as_view(), name='rider-update-location'),
]