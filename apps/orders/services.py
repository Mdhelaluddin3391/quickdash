import uuid
import logging
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from django.apps import apps
from django.shortcuts import get_object_or_404

from apps.utils.exceptions import BusinessLogicException
from apps.utils.utils import generate_order_id
from apps.inventory.services import InventoryService
from apps.warehouse.utils.warehouse_selector import WarehouseSelector
from apps.catalog.models import SKU
from apps.customers.models import Address
from .models import Order, OrderItem, OrderTimeline
from .signals import send_order_created

logger = logging.getLogger(__name__)

class CartService:
    """
    Handles secure cart retrieval using Django's get_model to avoid circular imports.
    """
    @staticmethod
    def get_active_cart_items(user):
        Cart = apps.get_model('orders', 'Cart')
        try:
            # Prefetch SKU to avoid N+1 during validation
            cart = Cart.objects.select_related('customer').prefetch_related('items__sku').get(customer=user)
        except Cart.DoesNotExist:
            raise BusinessLogicException("No active cart found.")

        if not cart.items.exists():
            raise BusinessLogicException("Cart is empty.")

        items = []
        for cart_item in cart.items.all():
            if cart_item.sku.is_active:
                items.append({
                    "sku_id": cart_item.sku.id,
                    "quantity": cart_item.quantity
                })
        
        if not items:
            raise BusinessLogicException("All items in your cart are currently unavailable.")
            
        return items

class OrderService:

    @staticmethod
    def create_order(user, address_id: str, items: list):
        """
        Secure Order Creation:
        1. Geo-Validate Location (Outside Atomic Block for Performance)
        2. Fetch SKUs & Calculate Price Server-Side (Security)
        3. Reserve Stock & Create Order (Atomic)
        """
        # [PERFORMANCE FIX] Step 1: Pre-Transaction Validation
        try:
            # Validate address belongs to user
            address = Address.objects.get(id=address_id, customer__user=user)
        except Address.DoesNotExist:
            raise BusinessLogicException("Invalid delivery address.")

        # Geo-Validation
        warehouse = WarehouseSelector.get_serviceable_warehouse(address.location.y, address.location.x)
        
        if not warehouse:
            logger.warning(f"Order Blocked: Location {address.pincode} out of service area.")
            raise BusinessLogicException("Sorry, we do not deliver to this location.")

        # [SECURITY FIX] Step 2: Atomic Logic
        with transaction.atomic():
            # A. Fetch SKUs from DB (Prevents Price Tampering)
            sku_ids = [item['sku_id'] for item in items]
            skus_map = SKU.objects.in_bulk(sku_ids)

            final_items = []
            total_amount = Decimal('0.00')
            inventory_payload = []

            for item in items:
                sku_id = item['sku_id']
                qty = item['quantity']

                sku = skus_map.get(sku_id)
                if not sku:
                    raise BusinessLogicException(f"Item {sku_id} is no longer available.")
                
                if not sku.is_active:
                    raise BusinessLogicException(f"Item {sku.name} is currently unavailable.")

                # TRUSTED PRICE CALCULATION
                line_total = sku.sale_price * qty
                total_amount += line_total

                final_items.append({
                    'sku': sku,
                    'quantity': qty,
                    'unit_price': sku.sale_price,
                    'total_price': line_total
                })
                
                inventory_payload.append({
                    "product_id": sku.id,
                    "quantity": qty
                })

            # B. Reserve Stock
            order_id = generate_order_id()
            InventoryService.reserve_stock(
                warehouse_id=warehouse.id,
                items=inventory_payload,
                reference=order_id
            )

            # C. Create Order
            order = Order.objects.create(
                id=order_id,
                user=user,
                warehouse_id=warehouse.id,
                delivery_address=address.as_dict(),
                total_amount=total_amount,
                status=Order.Status.PENDING
            )

            # D. Create Order Items
            order_items = [
                OrderItem(
                    order=order,
                    product_id=data['sku'].id,
                    product_name=data['sku'].name,
                    sku_code=data['sku'].sku_code,
                    quantity=data['quantity'],
                    unit_price=data['unit_price'],
                    total_price=data['total_price']
                ) for data in final_items
            ]
            OrderItem.objects.bulk_create(order_items)

            # E. Timeline
            OrderTimeline.objects.create(
                order=order, 
                status=Order.Status.PENDING, 
                description="Order created, waiting for payment."
            )

            return order

    @staticmethod
    @transaction.atomic
    def mark_order_paid(order_id: str, payment_id: str):
        """
        Transition: PENDING -> CONFIRMED
        """
        order = Order.objects.select_for_update().get(id=order_id)
        
        if order.status != Order.Status.PENDING:
            logger.warning(f"Order {order_id} already processed. Ignoring.")
            return order

        order.status = Order.Status.CONFIRMED
        order.payment_status = Order.PaymentStatus.PAID
        order.payment_id = payment_id
        order.save(update_fields=['status', 'payment_status', 'payment_id', 'updated_at'])

        OrderTimeline.objects.create(
            order=order, 
            status=Order.Status.CONFIRMED, 
            description="Payment received."
        )

        # Notify Warehouse (Async)
        items_payload = [
            {"product_id": str(i.product_id), "quantity": i.quantity} 
            for i in order.items.all()
        ]
        send_order_created.send(
            sender=Order, 
            order_id=order.id, 
            order_items=items_payload, 
            warehouse_id=order.warehouse_id
        )

        return order

    @staticmethod
    @transaction.atomic
    def cancel_order(order_id: str, reason: str = "User Cancelled"):
        """
        Handles Cancellation & Inventory Release.
        Triggers Refund if paid.
        """
        order = Order.objects.select_for_update().get(id=order_id)
        
        if not order.can_cancel:
            raise BusinessLogicException("Cannot cancel order at this stage.")

        # 1. Release Stock
        inventory_items = [
            {"product_id": i.product_id, "quantity": i.quantity}
            for i in order.items.all()
        ]
        InventoryService.release_stock(
            warehouse_id=order.warehouse_id,
            items=inventory_items,
            reference=f"CANCEL-{order.id}"
        )

        # 2. Trigger Refund (if paid)
        if order.payment_status == Order.PaymentStatus.PAID:
            from apps.payments.services import PaymentService
            PaymentService.initiate_refund(order) 
            order.payment_status = Order.PaymentStatus.REFUNDED

        # 3. Update Status
        order.status = Order.Status.CANCELLED
        order.save(update_fields=['status', 'payment_status', 'updated_at'])

        OrderTimeline.objects.create(
            order=order,
            status=Order.Status.CANCELLED,
            description=f"Cancelled: {reason}"
        )
        
        return order