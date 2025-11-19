import logging
from decimal import Decimal
import razorpay
import json
from django.db import transaction
from django.db.models import F, Avg
from django.utils import timezone
from django.conf import settings
from django.contrib.gis.measure import Distance
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

# --- App Imports (Adjusted for 'apps.' structure) ---
from apps.accounts.permissions import IsCustomer
from apps.catalog.models import SKU  # Using SKU instead of generic Product if needed
from apps.inventory.models import StoreInventory
from apps.delivery.models import Delivery
from apps.delivery.serializers import RiderDeliverySerializer
from apps.cart.models import Cart, CartItem
from apps.cart.serializers import CartSerializer

# Models
from .models import Order, OrderItem, Payment, Address, Coupon
from .serializers import (
    CheckoutSerializer,
    OrderDetailSerializer,
    OrderHistorySerializer,
    PaymentVerificationSerializer,
    RiderRatingSerializer
)

# Tasks (Ensure tasks.py exists in apps/orders)
# from .tasks import process_razorpay_refund_task 

logger = logging.getLogger(__name__)

def process_successful_payment(order_id):
    """
    Logic: Order CONFIRM karna aur WMS Tasks create karna.
    Yeh function 'Best' project ka core heart hai.
    """
    # Guarded imports to avoid circular error
    from apps.warehouse.models import BinInventory, PickingTask, PickItem # Check your warehouse models!
    from apps.accounts.models import User # Assuming staff are Users

    try:
        order = Order.objects.prefetch_related('items').get(
            pk=order_id, # Using pk or order_id field
            status="pending" # Ensure status string matches your model choices
        )
    except Order.DoesNotExist:
        logger.warning(f"Order {order_id} not found or already processed.")
        return False, "Order not found."

    try:
        with transaction.atomic():
            order_lock = Order.objects.select_for_update().get(pk=order.pk)
            order_items = order_lock.items.all()

            if not order_items.exists():
                raise Exception("Order has no items.")

            # 1. Update Order Status
            order_lock.status = "confirmed"
            order_lock.payment_status = "successful"
            order_lock.save()
            
            # 2. Payment Update
            payment = order_lock.payments.first()
            if payment:
                payment.status = "successful"
                payment.save()

            # 3. Create Delivery Task
            Delivery.objects.create(order=order_lock, status="pending")

            # 4. Clear Cart
            Cart.objects.filter(customer=order.customer).delete()

            # --- WMS LOGIC (Simplified for your structure) ---
            # 'Best' project used complex Greedy logic here.
            # Hum yahan basic warehouse task create karenge.
            
            warehouse = order_lock.warehouse # Ensure order has warehouse link
            if warehouse:
                # Create a Master Picking Task
                picking_task = PickingTask.objects.create(
                    order_id=str(order_lock.id),
                    warehouse=warehouse,
                    status='PENDING'
                )
                
                # Create Items for the task
                for item in order_items:
                    PickItem.objects.create(
                        task=picking_task,
                        sku=item.sku, # Ensure OrderItem has SKU link
                        qty_to_pick=item.quantity
                    )
                logger.info(f"WMS Task created for Order {order_id}")

            return True, "Success"

    except Exception as e:
        logger.error(f"Payment processing failed: {e}")
        return False, str(e)


class CheckoutView(generics.GenericAPIView):
    """
    Checkout: Calculates total, creates Pending Order, handles Razorpay/COD.
    """
    permission_classes = [IsAuthenticated, IsCustomer]
    serializer_class = CheckoutSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        data = serializer.validated_data
        payment_method = data.get('payment_method', 'RAZORPAY')
        
        # 1. Get Cart
        try:
            cart = Cart.objects.get(customer=user)
            if not cart.items.exists():
                return Response({"error": "Cart empty"}, status=400)
        except Cart.DoesNotExist:
             return Response({"error": "Cart not found"}, status=404)

        # 2. Calculate Totals (Simplified)
        # 'Best' project uses logic from settings
        item_subtotal = cart.total_price # Assuming property exists
        delivery_fee = settings.MIN_DELIVERY_FEE # Use settings!
        final_total = item_subtotal + delivery_fee
        
        # 3. Create Pending Order
        try:
            with transaction.atomic():
                order = Order.objects.create(
                    customer=user,
                    warehouse_id=data.get('warehouse_id'), # Frontend should send this
                    delivery_address_json=data.get('delivery_address_json'), # Or ID
                    total_amount=item_subtotal,
                    final_amount=final_total,
                    status="pending",
                    payment_status="pending"
                )
                
                # Move items from Cart to Order
                items_to_create = []
                for c_item in cart.items.all():
                    items_to_create.append(OrderItem(
                        order=order,
                        sku=c_item.sku,
                        quantity=c_item.quantity,
                        unit_price=c_item.sku.sale_price
                    ))
                OrderItem.objects.bulk_create(items_to_create)

        except Exception as e:
            return Response({"error": str(e)}, status=400)

        # 4. Handle Payment
        final_amount_paise = int(final_total * 100)

        if payment_method == 'COD':
            Payment.objects.create(order=order, payment_method='COD', amount=final_total)
            success, msg = process_successful_payment(order.id)
            if success:
                return Response({"message": "Order Confirmed (COD)", "order_id": order.id})
            return Response({"error": msg}, status=400)

        elif payment_method == 'RAZORPAY':
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            rzp_order = client.order.create({
                'amount': final_amount_paise,
                'currency': 'INR',
                'receipt': str(order.id)
            })
            
            Payment.objects.create(
                order=order, 
                payment_method='RAZORPAY',
                amount=final_total,
                razorpay_order_id=rzp_order['id']
            )
            
            return Response({
                "razorpay_order_id": rzp_order['id'],
                "razorpay_key": settings.RAZORPAY_KEY_ID,
                "amount": final_amount_paise,
                "order_id": order.id
            })

        return Response({"error": "Invalid Method"}, status=400)


class PaymentVerificationView(APIView):
    """
    Verifies Razorpay signature and confirms order.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        try:
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            client.utility.verify_payment_signature({
                'razorpay_order_id': data['razorpay_order_id'],
                'razorpay_payment_id': data['razorpay_payment_id'],
                'razorpay_signature': data['razorpay_signature']
            })
            
            # Find Payment object
            payment = Payment.objects.get(razorpay_order_id=data['razorpay_order_id'])
            payment.transaction_id = data['razorpay_payment_id']
            payment.save()
            
            # Process Order
            success, msg = process_successful_payment(payment.order.id)
            if success:
                return Response({"status": "Payment Successful, Order Confirmed"})
            else:
                return Response({"error": msg}, status=400)

        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return Response({"error": "Invalid Signature or Payment Failed"}, status=400)