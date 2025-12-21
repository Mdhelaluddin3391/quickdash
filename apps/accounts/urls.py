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
)

# REMOVED: LocationServiceCheckView from imports (It was redundant)

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
from .views_location import CheckServiceabilityView, SaveCurrentLocationView
from apps.delivery.views_api import UpdateRiderLocationView

urlpatterns = [
    # ==========================
    # AUTHENTICATION
    # ==========================
    path('auth/otp/send/', SendOTPView.as_view(), name='send-otp'),
    path('auth/otp/login/', LoginWithOTPView.as_view(), name='login-otp'),
    path('auth/google/login/', StaffGoogleLoginView.as_view(), name='staff-google-login'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),

    # ==========================
    # PROFILES & USER INFO
    # ==========================
    path('me/', MeView.as_view(), name='me'),
    path('customer/me/', CustomerMeView.as_view(), name='customer-me'),
    path('customer/addresses/', CustomerAddressListCreateView.as_view(), name='customer-address-list-create'),
    path('customer/addresses/<int:pk>/', CustomerAddressDetailView.as_view(), name='customer-address-detail'),
    path('customer/addresses/<int:pk>/set-default/', SetDefaultAddressView.as_view(), name='customer-address-set-default'),

    # ==========================
    # ADMIN / ONBOARDING
    # ==========================
    path("users/<uuid:user_id>/role/", ChangeUserRole.as_view()),
    path('onboarding/rider/apply/', RiderApplyView.as_view(), name='rider-apply'),
    path('admin/riders/', AdminRiderListView.as_view(), name='admin-rider-list'),
    path('admin/riders/<uuid:pk>/approve/', AdminApproveRiderView.as_view(), name='admin-approve-rider'),
    path('admin/riders/<uuid:pk>/reject/', AdminRejectRiderView.as_view(), name='admin-reject-rider'),
    path('admin/employees/', AdminEmployeeListCreateView.as_view(), name='admin-employee-list-create'),
    path('admin/employees/<uuid:pk>/status/', AdminEmployeeStatusUpdateView.as_view(), name='admin-employee-status-update'),

    # ==========================
    # LOCATION SERVICES (CLEANED)
    # ==========================
    # REMOVED: path('location/service-check/', ...) - It was a duplicate/unused
    
    # This is the one used by your Frontend JS
    path('location/check-serviceability/', CheckServiceabilityView.as_view(), name='check-serviceability'),
    path('location/save-current/', SaveCurrentLocationView.as_view(), name='save-current-location'),
    
    # RIDER ROUTES
    path('delivery/rider/update-location/', UpdateRiderLocationView.as_view(), name='rider-update-location'),
]