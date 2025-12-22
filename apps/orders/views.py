from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import ValidationError

from .models import Order
from .serializers import OrderSerializer, CreateOrderSerializer
from .services import OrderService

class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related('items')

    @action(detail=False, methods=['post'])
    def create_order(self, request):
        serializer = CreateOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            order = OrderService.create_order(
                user=request.user,
                cart_id=serializer.validated_data['cart_id'],
                address_id=serializer.validated_data['address_id'],
                payment_method=serializer.validated_data['payment_method']
            )
            return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)
        
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            # In production, log this error
            return Response({"error": "System error processing order."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        reason = request.data.get('reason', 'User cancelled')
        try:
            OrderService.cancel_order(pk, reason, user=request.user)
            return Response({"status": "Order cancelled successfully"})
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)