from django.urls import path
from .views import RiderProfileView, RiderStatusView, RiderLocationView

urlpatterns = [
    path('profile/', RiderProfileView.as_view(), name='rider-profile'),
    path('status/', RiderStatusView.as_view(), name='rider-status'),
    path('location/', RiderLocationView.as_view(), name='rider-location'),
]