from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Order, OrderItem, OrderTimeline
from .models.cart import Cart
from apps.inventory.services import InventoryService
from apps.warehouse.utils.warehouse_selector import WarehouseSelector

class OrderService:
    
    @staticmethod
    def create_order_from_cart(user, cart_id, payment_method, address_id):
        # 1. Validation
        try:
            cart = Cart.objects.get(id=cart_id, user=user, is_active=True)
        except Cart.DoesNotExist:
            raise ValidationError("Cart not found or empty")

        if not cart.items.exists():
            raise ValidationError("Cart is empty")

        # Select Warehouse (Geo-fencing logic)
        warehouse = WarehouseSelector.get_nearest_warehouse(user.default_address.location)
        if not warehouse:
            raise ValidationError("No warehouse serves this location")

        # 2. START ATOMIC TRANSACTION
        # Everything inside this block either succeeds fully or fails fully.
        with transaction.atomic():
            
            # 3. ACQUIRE LOCKS (The Fix)
            # Map products to quantities for bulk locking
            product_qty_map = {item.product.id: item.quantity for item in cart.items.all()}
            
            # This call will BLOCK if another user is buying these items, preventing race conditions
            InventoryService.bulk_lock_and_validate(product_qty_map, warehouse)

            # 4. Create Order
            total_amount = cart.total_price
            
            order = Order.objects.create(
                user=user,
                warehouse=warehouse,
                delivery_address=user.default_address,
                total_amount=total_amount,
                payment_method=payment_method,
                status='PENDING'
            )

            # 5. Create Items & Reserve Stock
            for item in cart.items.all():
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price=item.product.price
                )
                
                # We can safely reserve now because we hold the lock from step 3
                InventoryService.reserve_stock(
                    product=item.product, 
                    quantity=item.quantity, 
                    warehouse=warehouse,
                    reference=f"ORDER-{order.order_id}"
                )

            # 6. Deactivate Cart
            cart.is_active = False
            cart.save()
            
            # 7. Initial Timeline
            OrderTimeline.objects.create(
                order=order,
                status='PENDING',
                title='Order Placed',
                description='Your order has been placed successfully.'
            )

            return order

    @staticmethod
    def cancel_order(order):
        with transaction.atomic():
            if order.status in ['DELIVERED', 'CANCELLED']:
                raise ValidationError("Cannot cancel this order")
            
            # Release Stock
            for item in order.items.all():
                InventoryService.release_stock(
                    product=item.product,
                    quantity=item.quantity,
                    warehouse=order.warehouse,
                    reference=f"CANCEL-{order.order_id}"
                )
            
            order.status = 'CANCELLED'
            order.save()
            
            OrderTimeline.objects.create(
                order=order,
                status='CANCELLED',
                title='Order Cancelled',
                description='Order was cancelled.'
            )