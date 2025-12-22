# apps/orders/services.py

from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.inventory.services import InventoryService
from apps.warehouse.utils.warehouse_selector import WarehouseSelector
from apps.customers.models import Address
from apps.utils.utils import generate_code

from .models import Order, OrderItem, OrderTimeline, OrderStatus, Cart


class OrderService:

    @staticmethod
    def create_order(user, cart_id: str, address_id: int, payment_method: str):
        cart = Cart.objects.select_related().get(id=cart_id, user=user)
        if not cart.items.exists():
            raise ValidationError("Cart is empty")

        address = Address.objects.get(id=address_id, customer__user=user)
        location = address.location

        warehouse = WarehouseSelector.get_nearest_serviceable_warehouse(
            lat=location.y,
            lng=location.x,
        )
        if not warehouse:
            raise ValidationError("Service not available in your area")

        items = [
            {"product_id": i.product_id, "quantity": i.quantity}
            for i in cart.items.all()
        ]

        with transaction.atomic():
            InventoryService.bulk_lock_and_validate(
                warehouse_id=warehouse.id,
                items=items,
            )

            order = Order.objects.create(
                order_id=generate_code("ORD-"),
                user=user,
                warehouse=warehouse,
                total_amount=cart.total_price,
                status=OrderStatus.CREATED,
                delivery_address_snapshot=address.as_dict(),
            )

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

            InventoryService.reserve_stock(
                warehouse_id=warehouse.id,
                items=items,
                reference=f"ORDER-{order.order_id}",
            )

            OrderTimeline.objects.create(
                order=order,
                status=OrderStatus.CREATED,
                note="Order placed",
                created_by=user,
            )

            cart.items.all().delete()
            return order

    @staticmethod
    def confirm_payment(order_id: int, payment_id: str):
        with transaction.atomic():
            order = Order.objects.select_for_update().get(id=order_id)

            if order.status == OrderStatus.PAID:
                return order
            if order.status != OrderStatus.CREATED:
                raise ValidationError("Invalid order state")

            order.status = OrderStatus.PAID
            order.confirmed_at = timezone.now()
            order.save()

            OrderTimeline.objects.create(
                order=order,
                status=OrderStatus.PAID,
                note=f"Payment confirmed: {payment_id}",
            )

            return order

    @staticmethod
    def cancel_order(order_id: int, reason: str, user=None):
        with transaction.atomic():
            order = Order.objects.select_for_update().get(id=order_id)

            if order.status in (
                OrderStatus.DISPATCHED,
                OrderStatus.DELIVERED,
                OrderStatus.CANCELLED,
            ):
                raise ValidationError("Cannot cancel order")

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
            order.save()

            OrderTimeline.objects.create(
                order=order,
                status=OrderStatus.CANCELLED,
                note=reason,
                created_by=user,
            )

            return order
