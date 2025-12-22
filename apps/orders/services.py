# apps/orders/services.py

from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.inventory.services import InventoryService
from apps.customers.models import Address
from apps.warehouse.utils.warehouse_selector import WarehouseSelector
from apps.utils.utils import generate_code

from .models import Order, OrderItem, OrderTimeline, OrderStatus, Cart


class OrderService:
    """
    SINGLE ORCHESTRATOR for Order lifecycle.
    """

    @staticmethod
    def create_order(user, cart_id: str, address_id: str, payment_method: str) -> Order:
        # 1️⃣ Validate Cart
        try:
            cart = Cart.objects.select_related("user").get(id=cart_id, user=user)
        except Cart.DoesNotExist:
            raise ValidationError("Cart not found")

        if not cart.items.exists():
            raise ValidationError("Cart is empty")

        # 2️⃣ Resolve Address & GEO (SINGLE SOURCE)
        try:
            address = Address.objects.select_related("customer__user").get(
                id=address_id,
                customer__user=user,
            )
        except Address.DoesNotExist:
            raise ValidationError("Invalid or unauthorized address")

        location = address.location  # PointField

        # 3️⃣ Select Warehouse (Geo-based)
        warehouse = WarehouseSelector.get_nearest_serviceable_warehouse(
            lat=location.y,
            lng=location.x,
        )
        if not warehouse:
            raise ValidationError("Service not available in your area")

        # 4️⃣ Prepare Inventory Payload
        items = [
            {"product_id": i.product_id, "quantity": i.quantity}
            for i in cart.items.all()
        ]

        with transaction.atomic():
            # 5️⃣ Lock & Validate Inventory
            InventoryService.bulk_lock_and_validate(
                warehouse_id=warehouse.id,
                items=items,
            )

            # 6️⃣ Create Order
            order = Order.objects.create(
                order_id=generate_code(prefix="ORD-"),
                user=user,
                warehouse=warehouse,
                total_amount=cart.total_price,
                status=OrderStatus.CREATED,
                delivery_address_snapshot=address.as_dict(),
                payment_method=payment_method,
            )

            # 7️⃣ Create Order Items (Snapshot)
            OrderItem.objects.bulk_create([
                OrderItem(
                    order=order,
                    product=i.product,
                    sku_name_snapshot=i.product.name,
                    unit_price_snapshot=i.product.base_price,
                    quantity=i.quantity,
                )
                for i in cart.items.all()
            ])

            # 8️⃣ Reserve Inventory (Logical)
            InventoryService.reserve_stock(
                warehouse_id=warehouse.id,
                items=items,
                reference=f"ORDER-{order.order_id}",
            )

            # 9️⃣ Timeline
            OrderTimeline.objects.create(
                order=order,
                status=OrderStatus.CREATED,
                note="Order placed",
                created_by=user,
            )

            # 🔟 Cleanup Cart
            cart.items.all().delete()

            return order

    @staticmethod
    def confirm_payment(order_id: str, payment_id: str) -> Order:
        with transaction.atomic():
            order = Order.objects.select_for_update().get(id=order_id)

            if order.status == OrderStatus.PAID:
                return order  # idempotent

            if order.status != OrderStatus.CREATED:
                raise ValidationError("Invalid order state for payment confirmation")

            order.status = OrderStatus.PAID
            order.confirmed_at = timezone.now()
            order.save(update_fields=["status", "confirmed_at"])

            OrderTimeline.objects.create(
                order=order,
                status=OrderStatus.PAID,
                note=f"Payment confirmed: {payment_id}",
            )

            return order

    @staticmethod
    def cancel_order(order_id: str, reason: str, user=None) -> Order:
        with transaction.atomic():
            order = Order.objects.select_for_update().get(id=order_id)

            if order.status in (
                OrderStatus.DISPATCHED,
                OrderStatus.DELIVERED,
                OrderStatus.CANCELLED,
            ):
                raise ValidationError("Cannot cancel order in current state")

            items = [
                {"product_id": i.product_id, "quantity": i.quantity}
                for i in order.items.all()
            ]

            InventoryService.release_stock(
                warehouse_id=order.warehouse_id,
                items=items,
                reference=f"CANCEL-{order.order_id}",
            )

            order.status = OrderStatus.CANCELLED
            order.save(update_fields=["status"])

            OrderTimeline.objects.create(
                order=order,
                status=OrderStatus.CANCELLED,
                note=reason,
                created_by=user,
            )

            return order
