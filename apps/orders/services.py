import uuid
import logging
from django.db import transaction
from django.utils import timezone
from decimal import Decimal

from apps.utils.exceptions import BusinessLogicException
from apps.utils.utils import generate_order_id
from apps.inventory.services import InventoryService
from apps.warehouse.utils.warehouse_selector import WarehouseSelector
from .models import Order, OrderItem, OrderTimeline
from .signals import send_order_created

logger = logging.getLogger(__name__)

class OrderService:

    @staticmethod
    @transaction.atomic
    def create_order(user, address_data: dict, cart_items: list):
        """
        1. Geo-Validate Location
        2. Select Warehouse
        3. Reserve Stock
        4. Create Order
        """
        lat = address_data.get('lat')
        lng = address_data.get('lng')

        # [SECURITY FIX] Strict Server-Side Validation
        # The frontend provides lat/lng, but we MUST verify it falls inside a known polygon.
        # This prevents 'spoofed' coordinates that are technically valid but operationally wrong.
        
        from apps.warehouse.utils.warehouse_selector import WarehouseSelector
        
        # Use get_serviceable_warehouse which performs the Point-in-Polygon (PIP) check
        warehouse = WarehouseSelector.get_serviceable_warehouse(lat, lng)
        
        if not warehouse:
            # Reject outright if the coordinates are not inside any active ServiceArea polygon
            logger.warning(f"Order Blocked: Coordinates {lat},{lng} are out of bounds.")
            raise BusinessLogicException("Sorry, we do not deliver to this location.")

        # [ LOGIC CONTINUES... ]
        
        # Prep Inventory Payload
        inventory_items = []
        total_amount = Decimal('0.00')
        
        for item in cart_items:
            inventory_items.append({
                "product_id": item['product_id'],
                "quantity": item['quantity']
            })
            total_amount += Decimal(str(item['price'])) * item['quantity']

        # Reserve Stock
        order_id = generate_order_id()
        InventoryService.reserve_stock(
            warehouse_id=warehouse.id,
            items=inventory_items,
            reference=order_id
        )

        # Create Order
        order = Order.objects.create(
            id=order_id,
            user=user,
            warehouse_id=warehouse.id,
            delivery_address=address_data,
            total_amount=total_amount,
            status=Order.Status.PENDING
        )

        # Create Items
        order_items = [
            OrderItem(
                order=order,
                product_id=i['product_id'],
                product_name=i['product_name'],
                sku_code=i['sku_code'],
                quantity=i['quantity'],
                unit_price=i['price'],
                total_price=Decimal(str(i['price'])) * i['quantity']
            ) for i in cart_items
        ]
        OrderItem.objects.bulk_create(order_items)

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
            PaymentService.initiate_refund(order) # Will handle async
            order.payment_status = Order.PaymentStatus.REFUNDED

        # 3. Update Status
        previous_status = order.status
        order.status = Order.Status.CANCELLED
        order.save(update_fields=['status', 'payment_status', 'updated_at'])

        OrderTimeline.objects.create(
            order=order,
            status=Order.Status.CANCELLED,
            description=f"Cancelled: {reason}"
        )
        
        return order