from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.utils.utils import generate_code  # Assumed utility
from apps.inventory.services import InventoryService
from apps.warehouse.utils.warehouse_selector import WarehouseSelector
from .models import Order, OrderItem, OrderTimeline, OrderStatus, Cart

class OrderService:
    
    @staticmethod
    def create_order(user, cart_id: str, address_id: int, payment_method: str) -> Order:
        """
        Orchestrates atomic order creation:
        1. Validate Cart
        2. Select Warehouse
        3. Lock Inventory
        4. Create DB Records
        5. Reserve Stock
        """
        # 1. Fetch & Validate Cart
        try:
            cart = Cart.objects.get(id=cart_id, user=user)
            if not cart.items.exists():
                raise ValidationError("Cart is empty.")
        except Cart.DoesNotExist:
            raise ValidationError("Cart not found.")

        # 2. Routing Logic (Find Warehouse)
        # Assuming address logic fetches coords
        # warehouse = WarehouseSelector.select_best_warehouse(cart.items.all(), user_coords)
        # For simplicity in this snippet, we assume warehouse is resolved or passed
        warehouse = WarehouseSelector.get_serviceable_warehouse(lat=12.97, lng=77.59) # Mock coords
        if not warehouse:
            raise ValidationError("No service in your area.")

        # 3. Prepare Data for Locking
        product_qty_map = {item.product.id: item.quantity for item in cart.items.all()}

        with transaction.atomic():
            # 4. PESSIMISTIC LOCKING via InventoryService
            # This ensures stocks don't change while we are creating the order
            InventoryService.bulk_lock_and_validate(product_qty_map, warehouse)

            # 5. Create Order Header
            order = Order.objects.create(
                order_id=generate_code(prefix="ORD-"),
                user=user,
                warehouse=warehouse,
                total_amount=cart.total_price,  # Assumed property on Cart
                status=OrderStatus.CREATED,
                delivery_address_snapshot={"address_id": address_id} # Simplified
            )

            # 6. Create Items & Reserve Stock
            for item in cart.items.all():
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    sku_name_snapshot=item.product.name,
                    unit_price_snapshot=item.product.base_price,
                    quantity=item.quantity
                )
                
                # Explicit Service Call for Reservation
                InventoryService.reserve_stock(
                    product=item.product,
                    quantity=item.quantity,
                    warehouse=warehouse,
                    reference=f"ORDER-{order.order_id}"
                )

            # 7. Log Timeline
            OrderTimeline.objects.create(
                order=order,
                status=OrderStatus.CREATED,
                note="Order placed successfully.",
                created_by=user
            )

            # 8. Cleanup Cart
            cart.items.all().delete()
            
            # Note: Signals for notifications are fired implicitly by post_save if configured,
            # or we can fire them explicitly here if we want 100% control.
            
            return order

    @staticmethod
    def confirm_payment(order_id: str, payment_id: str):
        """
        Transition: CREATED -> PAID
        """
        with transaction.atomic():
            order = Order.objects.select_for_update().get(id=order_id)
            
            if order.status != OrderStatus.CREATED:
                # Idempotency check: if already paid, just return
                if order.status == OrderStatus.PAID:
                    return order
                raise ValidationError(f"Invalid state transition from {order.status} to PAID")

            order.status = OrderStatus.PAID
            order.confirmed_at = timezone.now()
            order.save()

            OrderTimeline.objects.create(
                order=order,
                status=OrderStatus.PAID,
                note=f"Payment confirmed via {payment_id}"
            )
            return order

    @staticmethod
    def dispatch_order(order_id: str):
        """
        Transition: PAID -> DISPATCHED
        """
        with transaction.atomic():
            order = Order.objects.select_for_update().get(id=order_id)
            
            if order.status != OrderStatus.PAID:
                raise ValidationError("Order must be PAID before dispatch.")

            order.status = OrderStatus.DISPATCHED
            order.save()

            OrderTimeline.objects.create(
                order=order,
                status=OrderStatus.DISPATCHED,
                note="Order dispatched from warehouse."
            )
            return order

    @staticmethod
    def cancel_order(order_id: str, reason: str, user=None):
        """
        Transition: ANY -> CANCELLED
        Releases inventory.
        """
        with transaction.atomic():
            order = Order.objects.select_for_update().get(id=order_id)
            
            if order.status in [OrderStatus.DISPATCHED, OrderStatus.DELIVERED, OrderStatus.CANCELLED]:
                raise ValidationError("Cannot cancel order in current state.")

            # Release Inventory
            for item in order.items.all():
                InventoryService.release_stock(
                    product=item.product,
                    quantity=item.quantity,
                    warehouse=order.warehouse,
                    reference=f"CANCEL-{order.order_id}"
                )

            order.status = OrderStatus.CANCELLED
            order.save()

            OrderTimeline.objects.create(
                order=order,
                status=OrderStatus.CANCELLED,
                note=f"Cancelled. Reason: {reason}",
                created_by=user
            )
            return order