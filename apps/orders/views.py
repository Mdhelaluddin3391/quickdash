from rest_framework import viewsets, views, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Order
from .serializers import OrderSerializer, CreateOrderSerializer
from .services import OrderService, CartService
from apps.customers.models import Address

class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # [OPTIMIZATION FIX] Prevent N+1 queries by prefetching related items and timeline
        return Order.objects.filter(user=self.request.user)\
            .select_related('warehouse')\
            .prefetch_related('items', 'timeline')\
            .order_by('-created_at')

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        try:
            OrderService.cancel_order(pk)
            return Response({"status": "Order Cancelled"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class CreateOrderView(views.APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # We only validate address_id, items are fetched from DB cart for security
        address_id = request.data.get('address_id')
        if not address_id:
            return Response({"error": "Address ID is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # 1. Fetch Verified Cart Data (Server-Side)
            cart_items = CartService.get_active_cart_items(request.user)
            
            # 2. Create Order
            order = OrderService.create_order(
                user=request.user,
                address_id=address_id,
                items=cart_items
            )
            
            # 3. Initiate Payment
            from apps.payments.services import PaymentService
            payment_payload = PaymentService.create_payment_order(order)
            
            return Response({
                "order_id": order.id,
                "payment": payment_payload
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)