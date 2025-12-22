from rest_framework import viewsets, views, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Order
from .serializers import OrderSerializer, CreateOrderSerializer
from .services import OrderService
from apps.customers.models import Address

class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).order_by('-created_at')

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
        serializer = CreateOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            # Fetch Address snapshot
            address = Address.objects.get(
                id=serializer.validated_data['address_id'], 
                customer__user=request.user
            )
            
            # Fetch Cart (Simplified for MVP, usually passed or fetched from DB)
            cart_items = serializer.validated_data['items']
            
            order = OrderService.create_order(
                user=request.user,
                address_data=address.as_dict(),
                cart_items=cart_items
            )
            
            # Initiate Payment (Step 6 will hook here)
            from apps.payments.services import PaymentService
            payment_payload = PaymentService.create_payment_order(order)
            
            return Response({
                "order_id": order.id,
                "payment": payment_payload
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)