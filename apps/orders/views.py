# apps/orders/views.py

from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import Order
from .serializers import OrderSerializer, CreateOrderSerializer
from .services import OrderService


class OrderViewSet(ReadOnlyModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)

    def create(self, request):
        serializer = CreateOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order = OrderService.create_order(
            user=request.user,
            cart_id=serializer.validated_data["cart_id"],
            address_id=serializer.validated_data["address_id"],
            payment_method=serializer.validated_data["payment_method"],
        )

        return Response(
            OrderSerializer(order).data,
            status=status.HTTP_201_CREATED,
        )
