from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'picking', views.PickingTaskViewSet, basename='picking')
router.register(r'packing', views.PackingTaskViewSet, basename='packing')

urlpatterns = [
    path('', include(router.urls)),
    path('picking/scan/', views.ScanPickView.as_view(), name='scan-pick'),
    path('packing/<uuid:pk>/complete/', views.CompletePackingView.as_view(), name='complete-packing'),
]