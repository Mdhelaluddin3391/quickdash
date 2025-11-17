from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

# Hamare apne apps se import
from apps.accounts.permissions import IsCustomer
from apps.inventory.models import SKU
# from apps.warehouse.signals import send_order_created # FIX: Yahaan se signal hata diya
from .models import Order, OrderItem, OrderTimeline
from .serializers import (
    CreateOrderSerializer,
    OrderSerializer,
    OrderListSerializer
)

import logging
logger = logging.getLogger(__name__)


class CreateOrderAPIView(APIView):
    """
    Naya order create karne ke liye main API.
    Yeh sirf order ko "pending" state mein banayega.
    POST /api/v1/orders/create/
    """
    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request, *args, **kwargs):
        serializer = CreateOrderSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated_data = serializer.validated_data
        items_data = validated_data.pop('items')
        
        try:
            # Step 1: Database transaction shuru karein
            with transaction.atomic():
                
                # Step 2: Order ki keemat (Pricing) calculate karein
                total_amount = 0
                order_items_to_create = []

                for item_data in items_data:
                    sku_id = item_data['sku_id']
                    quantity = item_data['quantity']
                    
                    # TODO: Asli system mein, price SKU se lein.
                    # sku = SKU.objects.get(id=sku_id)
                    # unit_price = sku.sale_price
                    
                    unit_price = 10.00  # <-- FAKE PRICE (ABHI KE LIYE)
                    
                    item_total = unit_price * quantity
                    total_amount += item_total
                    
                    # OrderItem object ko create list mein add karein
                    order_items_to_create.append(
                        OrderItem(
                            # order=order, (yeh neeche set hoga)
                            sku_id=sku_id,
                            quantity=quantity,
                            unit_price=unit_price,
                        )
                    )

                # Step 3: Order object banayein (Pending state mein)
                
                # FIX: Status "pending" hoga
                payment_status = "pending"
                order_status = "pending" 
                
                order = Order.objects.create(
                    customer=request.user,
                    warehouse_id=validated_data['warehouse_id'],
                    delivery_address_json=validated_data['delivery_address_json'],
                    status=order_status,
                    payment_status=payment_status,
                    total_amount=total_amount,
                    discount_amount=0, 
                    final_amount=total_amount
                )
                
                # Step 4: Order items ko Order se link karke bulk create karein
                for item in order_items_to_create:
                    item.order = order
                OrderItem.objects.bulk_create(order_items_to_create)
                
                # Step 5: Order ki history (timeline) mein pehli entry daalein
                OrderTimeline.objects.create(
                    order=order,
                    status=order_status,
                    notes="Order created and awaiting payment."
                )

            # --- Transaction (Database ka kaam) poora hua ---

            # FIX: WMS ko signal bhejna yahaan se HATA diya gaya hai.
            # Signal ab 'VerifyPaymentAPIView' bhejega.

            # Step 6: Customer ko Order ID aur Amount waapas bhejein
            # taaki woh payment API ko call kar sake.
            return Response({
                "order_id": order.id,
                "final_amount": order.final_amount,
                "status": order.status,
                "payment_status": order.payment_status,
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            # Agar transaction ke dauraan koi bhi error aata hai
            logger.exception(f"Order creation failed for user {request.user.id}: {e}")
            return Response(
                {"detail": f"An error occurred while creating the order: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class OrderHistoryAPIView(generics.ListAPIView):
    """
    Customer ke puraane orders ki list.
    GET /api/v1/orders/
    """
    permission_classes = [IsAuthenticated, IsCustomer]
    serializer_class = OrderListSerializer

    def get_queryset(self):
        # Sirf usi customer ke orders dikhayein jo logged in hai
        return Order.objects.filter(customer=self.request.user)


class OrderDetailAPIView(generics.RetrieveAPIView):
    """
    Ek specific order ki poori detail.
    GET /api/v1/orders/<uuid:id>/
    """
    permission_classes = [IsAuthenticated, IsCustomer]
    serializer_class = OrderSerializer
    lookup_field = 'id' # URL se 'id' parameter lega

    def get_queryset(self):
        # Customer sirf apne hi orders dekh sakta hai
        return Order.objects.filter(customer=self.request.user).prefetch_related(
            'items__sku', 'timeline'
        )