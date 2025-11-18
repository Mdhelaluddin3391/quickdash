# apps/analytics/urls.py
from django.urls import path
from .views import DailyKPIListView

urlpatterns = [
    # GET /api/v1/analytics/kpis/
    path('kpis/', DailyKPIListView.as_view(), name='daily-kpis'),
]