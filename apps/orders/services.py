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
    Uses PostGIS to find the nearest active warehouse within radius.
    """
    MAX_RADIUS_KM = getattr(settings, 'DELIVERY_RADIUS_KM', 15.0)
    
    if not lat or not lng:
        return None, float('inf')

    try:
        user_location = Point(float(lng), float(lat), srid=4326)
        
        nearest_wh = Warehouse.objects.filter(
            is_active=True,
            location__distance_lte=(user_location, D(km=MAX_RADIUS_KM))
        ).annotate(
            distance=Distance('location', user_location)
        ).order_by('distance').first()

        if nearest_wh:
            # Handle distance object safely
            dist_val = nearest_wh.distance.km if hasattr(nearest_wh.distance, 'km') else 0.0
            return nearest_wh, dist_val
            
    except (ValueError, TypeError) as e:
        logger.error(f"Geo query error for {lat},{lng}: {e}")
        
    return None, float('inf')

def create_order_from_cart(user, warehouse_id, delivery_address_json, delivery_lat=None, delivery_lng=None, payment_method='RAZORPAY'):
    # 1. Warehouse Selection
    selected_warehouse = None
    if delivery_lat and delivery_lng:
        nearest_wh, distance = get_nearest_warehouse(delivery_lat, delivery_lng)
        if not nearest_wh:
            return None, None, "We do not deliver to this location (No warehouse nearby)."
        selected_warehouse = nearest_wh
    else:
        # Manual ID fallback
        if not warehouse_id:
            return None, None, "Delivery location or Warehouse ID is required."
        try:
            selected_warehouse = Warehouse.objects.get(id=warehouse_id, is_active=True)
        except Warehouse.DoesNotExist:
            return None, None, "Selected warehouse does not exist or is inactive."

    # 2. Get Cart
    try:
        cart = Cart.objects.select_related('customer').prefetch_related('items__sku').get(customer=user)
    except Cart.DoesNotExist:
        return None, None, "Cart not found"

    if not cart.items.exists():
        return None, None, "Cart empty"

    # 3. ATOMIC TRANSACTION: Lock Stock -> Create Order
    try:
        with transaction.atomic():
            # A. Lock Inventory
            for item in cart.items.select_for_update():
                try:
                    # This function must perform a DB-level lock/update
                    check_and_lock_inventory(selected_warehouse.id, item.sku.id, item.quantity)
                except ValueError as e:
                    logger.warning(f"Stock checkout failed for user {user.id}: {e}")
                    return None, None, f"Out of Stock: {str(e)}"

            # B. Create Order
            order = Order.objects.create(
                customer=user,
                warehouse=selected_warehouse,
                delivery_address_json=delivery_address_json,
                delivery_lat=delivery_lat,
                delivery_lng=delivery_lng,
                status='pending',
                payment_status='pending',
            )

            # C. Create Order Items
            items_to_create = []
            for c_item in cart.items.all():
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
            
            # D. Update Totals
            order.recalculate_totals(save=True)

            # E. Handle Payment Placeholder
            payment = None
            if payment_method == 'COD':
                payment = Payment.objects.create(
                    order=order, 
                    payment_method=Payment.PaymentMethod.COD, 
                    amount=order.final_amount,
                    status=Payment.PaymentStatus.PENDING 
                )
            
            return order, payment, None

    except Exception as e:
        logger.exception(f"Critical error during order creation for user {user.id}")
        return None, None, "An internal error occurred while placing the order."

def process_successful_payment(order):
    """
    Called after COD confirmation or Razorpay webhook success.
    Triggers WMS flow.
    """
    try:
        with transaction.atomic():
            # 1. Update Order
            order.status = "confirmed"
            order.payment_status = "paid"
            order.confirmed_at = timezone.now() # Record timestamp
            order.save(update_fields=["status", "payment_status", "confirmed_at"])

            # 2. Update Payment
            payment = order.payments.first()
            if payment and payment.status != Payment.PaymentStatus.SUCCESSFUL:
                payment.status = Payment.PaymentStatus.SUCCESSFUL
                payment.save(update_fields=["status"])

            # 3. Prepare Payload
            wms_items_list = [
                {"sku_id": str(item.sku.id), "qty": item.quantity}
                for item in order.items.all().select_related('sku')
            ]
            
            # 4. Trigger WMS Signal (On Commit only)
            def trigger_wms_signal():
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

            transaction.on_commit(trigger_wms_signal)
            
            return True, "Success"
    except Exception as e:
        logger.exception(f"Payment processing failed: {e}")
        return False, str(e)

def cancel_order(order, cancelled_by=None, reason=""):
    from .models import OrderTimeline, OrderCancellation
    
    if order.status in ['cancelled', 'delivered']:
        return False, 'Cannot cancel order in its current state.'

    try:
        with transaction.atomic():
            order.status = 'cancelled'
            order.cancelled_at = timezone.now()
            order.save(update_fields=['status', 'cancelled_at'])

            OrderTimeline.objects.create(order=order, status='cancelled', notes=reason or '')
            
            OrderCancellation.objects.create(
                order=order,
                reason=reason or '',
                cancelled_by=cancelled_by if isinstance(cancelled_by, str) else 'OPS'
            )

            if order.payment_status == 'paid':
                from apps.orders.signals import order_refund_requested
                # Signal for refund
                transaction.on_commit(lambda: order_refund_requested.send(
                    sender=order.__class__,
                    order_id=order.id,
                    amount=order.final_amount,
                    reason=reason,
                ))
                
        return True, None
    except Exception as e:
        logger.exception(f"Cancel failed: {e}")
        return False, str(e)