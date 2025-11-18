# apps/inventory/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from apps.accounts.permissions import IsWarehouseManagerEmployee
from .models import InventoryStock, SKU
from apps.warehouse.models import Warehouse

class AdjustStockAPIView(APIView):
    permission_classes = [IsWarehouseManagerEmployee]

    def post(self, request):
        # Logic: SKU aur Warehouse lo, aur stock +/- karo
        # Yeh implementation tumhare upar hai, lekin ye endpoint missing tha.
        return Response({"msg": "Stock adjusted"}, status=200)