import logging
from decimal import Decimal
from django.db import transaction
from django.conf import settings
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D

from apps.orders.models import Order, OrderItem, Cart
from apps.payments.models import Payment
from apps.warehouse.models import Warehouse
from apps.inventory.services import check_and_lock_inventory
from apps.orders.signals import send_order_created
from apps.payments.signals import payment_succeeded as payments_payment_succeeded

logger = logging.getLogger(__name__)


def get_nearest_warehouse(lat, lng):
    """
    [PERFORMANCE FIX] Uses PostGIS Database Distance calculation.
    """
    MAX_RADIUS_KM = 15.0
    
    if not lat or not lng:
        return None, float('inf')

    # Create Point object
    user_location = Point(float(lng), float(lat), srid=4326)

    # 1. Filter active warehouses
    # 2. Filter within radius (distance_lte uses spatial index)
    # 3. Annotate with precise distance
    # 4. Order by distance
    nearest_wh = Warehouse.objects.filter(
        is_active=True,
        location__distance_lte=(user_location, D(km=MAX_RADIUS_KM))
    ).annotate(
        distance=Distance('location', user_location)
    ).order_by('distance').first()

    if nearest_wh:
        # distance.km property might be available depending on Django version/backend
        # safely return distance object or float
        dist_val = nearest_wh.distance.km if hasattr(nearest_wh.distance, 'km') else 0.0
        return nearest_wh, dist_val
            
    return None, float('inf')


def process_successful_payment(order):
    try:
        with transaction.atomic():
            # 1. Update Order Status
            order.status = "confirmed"
            order.payment_status = "paid"
            order.save(update_fields=["status", "payment_status"])

            # 2. Update Payment Record
            payment = order.payments.first()
            if payment:
                payment.status = Payment.PaymentStatus.SUCCESSFUL
                payment.save(update_fields=["status"])

            # 3. Prepare WMS Payload
            wms_items_list = [
                {"sku_id": str(item.sku.id), "qty": item.quantity}
                for item in order.items.all().select_related('sku')
            ]
            
            # 4. Define the trigger function
            def trigger_wms_signal():
                try:
                    send_order_created.send(
                        sender=order.__class__,
                        order_id=order.id,
                        order_items=wms_items_list,
                        metadata={
                            "warehouse_id": str(order.warehouse.id) if order.warehouse else None,
                            "customer_id": str(order.customer.id) if order.customer else None,
                        }
                    )
                    logger.info(f"WMS signal sent for confirmed order {order.id}")
                except Exception:
                    logger.exception("Failed to send WMS signal")

            # 5. Execute ONLY after commit
            transaction.on_commit(trigger_wms_signal)

            # 6. Notify Payments App
            transaction.on_commit(lambda: payments_payment_succeeded.send(sender=order.__class__, order=order))

            return True, "Success"
    except Exception as e:
        logger.exception(f"Payment processing failed: {e}")
        return False, str(e)


def create_order_from_cart(user, warehouse_id, delivery_address_json, delivery_lat=None, delivery_lng=None, payment_method='RAZORPAY'):
    # 1. Warehouse Selection Logic
    selected_warehouse = None
    
    if delivery_lat and delivery_lng:
        # Automatic: Find nearest warehouse
        nearest_wh, distance = get_nearest_warehouse(delivery_lat, delivery_lng)
        
        if not nearest_wh:
            return None, None, "We do not deliver to this location (No warehouse nearby)."
        selected_warehouse = nearest_wh
        
    else:
        # Fallback: Manual ID (Ensure it's valid)
        if not warehouse_id:
            return None, None, "Delivery location or Warehouse ID is required."
            
        try:
            selected_warehouse = Warehouse.objects.get(id=warehouse_id, is_active=True)
        except Warehouse.DoesNotExist:
            return None, None, "Selected warehouse does not exist or is inactive."

    # 2. Get Cart with related SKU data to prevent N+1
    try:
        cart = Cart.objects.select_related('customer').prefetch_related('items__sku').get(customer=user)
    except Cart.DoesNotExist:
        return None, None, "Cart not found"

    if not cart.items.exists():
        return None, None, "Cart empty"

    try:
        with transaction.atomic():
            # 3. Lock Inventory First (Critical for avoiding Race Conditions)
            for item in cart.items.all():
                try:
                    # check_and_lock_inventory must handle 'select_for_update' on InventoryStock
                    check_and_lock_inventory(selected_warehouse.id, item.sku.id, item.quantity)
                except ValueError as e:
                    # Specific business logic error (Stock unavailable)
                    logger.warning(f"Stock checkout failed for user {user.id}: {e}")
                    return None, None, f"Out of Stock: {str(e)}"

            # 4. Create Order
            order = Order.objects.create(
                customer=user,
                warehouse=selected_warehouse,
                delivery_address_json=delivery_address_json,
                delivery_lat=delivery_lat,
                delivery_lng=delivery_lng,
                status='pending',
                payment_status='pending',
            )

            # 5. Create Order Items
            items_to_create = []
            for c_item in cart.items.all():
                # Priority: Use current SKU price to ensure accuracy at moment of purchase
                unit_price = c_item.sku.sale_price or Decimal("0.00")
                
                items_to_create.append(
                    OrderItem(
                        order=order,
                        sku=c_item.sku,
                        quantity=c_item.quantity,
                        unit_price=unit_price,
                        total_price=unit_price * c_item.quantity,
                        sku_name_snapshot=c_item.sku.name,
                    )
                )
            OrderItem.objects.bulk_create(items_to_create)
            
            # 6. Update Totals (Calculates taxes, delivery fees, discounts)
            order.recalculate_totals(save=True)

            # 7. Handle COD Payment
            payment = None
            if payment_method == 'COD':
                payment = Payment.objects.create(
                    order=order, 
                    payment_method=Payment.PaymentMethod.COD, 
                    amount=order.final_amount,
                    status=Payment.PaymentStatus.PENDING 
                )
            
            # Note: Cart is NOT deleted here. 
            # It should be deleted only after Payment Confirmation (in views/webhooks).
                
            return order, payment, None

    except Exception as e:
        logger.exception(f"Critical error during order creation for user {user.id}")
        return None, None, "An internal error occurred while placing the order."


def cancel_order(order, cancelled_by=None, reason=""):
    from .models import OrderTimeline, OrderCancellation
    try:
        if order.status in ['cancelled', 'delivered']:
            return False, 'Cannot cancel order in its current state.'

        order.status = 'cancelled'
        order.save(update_fields=['status'])

        OrderTimeline.objects.create(order=order, status='cancelled', notes=reason or '')
        
        OrderCancellation.objects.create(
            order=order,
            reason=reason or '',
            cancelled_by=cancelled_by if isinstance(cancelled_by, str) else 'OPS'
        )

        if order.payment_status == 'paid':
            from apps.orders.signals import order_refund_requested
            order_refund_requested.send(
                sender=order.__class__,
                order_id=order.id,
                amount=order.final_amount,
                reason=reason,
            )
        return True, None
    except Exception as e:
        logger.exception(f"Cancel failed: {e}")
        return False, str(e)