# apps/analytics/views.py
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from apps.accounts.permissions import IsAdmin # Strictest permission for analytics
from .models import DailyKPI
from .serializers import DailyKPISerializer

class DailyKPIListView(generics.ListAPIView):
    """
    GET /api/v1/analytics/kpis/
    Admin users ke liye Daily KPIs ki list.
    """
    permission_classes = [IsAuthenticated, IsAdmin] 
    serializer_class = DailyKPISerializer
    queryset = DailyKPI.objects.all().select_related('warehouse')
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Simple filters (jaise date range ya warehouse)
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        warehouse_id = self.request.query_params.get('warehouse_id')
        
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
        if warehouse_id:
            queryset = queryset.filter(warehouse_id=warehouse_id)
            
        return queryset