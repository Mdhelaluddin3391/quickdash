from django.db import transaction
from django.utils import timezone
from .models.order import Order, OrderStatus
from .models.item import OrderItem
from .models.cart import Cart
from apps.inventory.services import InventoryService
from apps.warehouse.utils.warehouse_selector import get_nearest_warehouse
from apps.customers.services import CustomerService
from apps.utils.exceptions import BusinessLogicException

class OrderService:
    @staticmethod
    @transaction.atomic
    def create_order_from_cart(user, address_id, lat, lng):
        """
        1. Validate Warehouse
        2. Validate Cart
        3. Lock Inventory (Reserve)
        4. Create Order
        """
        # 1. Get Cart
        try:
            cart = Cart.objects.get(user=user)
            cart_items = cart.items.select_related('product').all()
            if not cart_items:
                raise BusinessLogicException("Cart is empty")
        except Cart.DoesNotExist:
            raise BusinessLogicException("Cart is empty")

        # 2. Determine Warehouse
        warehouse = get_nearest_warehouse(lat, lng)
        if not warehouse:
            raise BusinessLogicException("No service in this location")

        # 3. Get Address
        try:
            profile = CustomerService.get_or_create_profile(user)
            address = profile.addresses.get(id=address_id)
            address_snapshot = {
                "line1": address.address_line_1,
                "city": address.city,
                "lat": str(address.latitude),
                "lng": str(address.longitude)
            }
        except Exception:
            raise BusinessLogicException("Invalid delivery address")

        # 4. Calculate Totals & Reserve Stock
        total_amount = 0
        order_items_data = []

        for item in cart_items:
            # Atomic Reservation via Inventory App
            InventoryService.reserve_stock(
                warehouse_id=warehouse.id,
                product_id=item.product.id,
                qty=item.quantity,
                order_id="TEMP" # Will link after creation
            )
            
            line_total = item.product.base_price * item.quantity
            total_amount += line_total
            
            order_items_data.append({
                "product": item.product,
                "qty": item.quantity,
                "price": item.product.base_price,
                "name": item.product.name
            })

        # 5. Create DB Record
        order = Order.objects.create(
            user=user,
            warehouse=warehouse,
            total_amount=total_amount,
            delivery_address_snapshot=address_snapshot,
            status=OrderStatus.PENDING_PAYMENT
        )

        for data in order_items_data:
            OrderItem.objects.create(
                order=order,
                product=data['product'],
                quantity=data['qty'],
                unit_price_snapshot=data['price'],
                product_name_snapshot=data['name']
            )

        # 6. Clear Cart
        cart.items.all().delete()

        return order

    @staticmethod
    def mark_order_as_paid(order_id, payment_id):
        """
        Triggered by Payment Webhook/Signal.
        Confirm stock deduction and move state.
        """
        with transaction.atomic():
            order = Order.objects.select_for_update().get(id=order_id)
            
            if order.status != OrderStatus.PENDING_PAYMENT:
                return order # Idempotency check
            
            # Confirm Inventory Deduction
            for item in order.items.all():
                InventoryService.confirm_stock_deduction(
                    warehouse_id=order.warehouse.id,
                    product_id=item.product.id,
                    qty=item.quantity,
                    order_id=order.id
                )
            
            order.status = OrderStatus.PAID
            order.payment_id = payment_id
            order.confirmed_at = timezone.now()
            order.save()
            
            # Signal to notify Warehouse/Rider System would go here
            return order

    @staticmethod
    def cancel_order(order_id):
        """
        Releases stock reservation.
        """
        with transaction.atomic():
            order = Order.objects.select_for_update().get(id=order_id)
            
            if order.status == OrderStatus.CANCELLED:
                return
            
            if order.status == OrderStatus.PENDING_PAYMENT:
                # Release Stock
                for item in order.items.all():
                    InventoryService.release_reservation(
                        warehouse_id=order.warehouse.id,
                        product_id=item.product.id,
                        qty=item.quantity
                    )
            
            order.status = OrderStatus.CANCELLED
            order.save()