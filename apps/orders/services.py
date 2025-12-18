# apps/orders/services.py
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D

from apps.orders.models import Order, OrderItem, Cart
from apps.payments.models import Payment
from apps.warehouse.models import Warehouse
from apps.inventory.services import check_and_lock_inventory
from apps.orders.signals import send_order_created
from apps.payments.services import create_razorpay_order

logger = logging.getLogger(__name__)


class CheckoutOrchestrator:
    def __init__(self, user, data):
        self.user = user
        self.data = data
        self.warehouse_id = data.get("warehouse_id")
        self.delivery_address = data.get("delivery_address_json")
        self.lat = data.get("delivery_lat")
        self.lng = data.get("delivery_lng")
        self.payment_method = data.get("payment_method", "RAZORPAY")

    # ---------------------------------------------
    # GET WAREHOUSE
    # ---------------------------------------------
    def _get_warehouse(self):
        # Try geo-based lookup
        if self.lat and self.lng:
            wh, dist = get_nearest_warehouse(self.lat, self.lng)
            if wh:
                logger.info(f"[Warehouse] Geo-located {wh.code} @ {dist}km")
                return wh

        # Fallback ID
        if self.warehouse_id:
            try:
                return Warehouse.objects.get(id=self.warehouse_id, is_active=True)
            except Warehouse.DoesNotExist:
                logger.warning(f"Invalid warehouse requested: {self.warehouse_id}")

        return None

    # ---------------------------------------------
    # EXECUTE CHECKOUT
    # ---------------------------------------------
    # ---------------------------------------------
    # EXECUTE CHECKOUT
    # ---------------------------------------------
    def execute(self):
        # 1. Validate warehouse
        warehouse = self._get_warehouse()
        if not warehouse:
            return None, None, "No serviceable warehouse found for this location."

        # 2. Validate cart exists
        try:
            cart = Cart.objects.select_related('customer').prefetch_related('items__sku').get(customer=self.user)
        except Cart.DoesNotExist:
            return None, None, "Cart not found."

        if not cart.items.exists():
            return None, None, "Cart is empty."

        # 3. FIX: Check for duplicate order in last 30 seconds (Idempotency)
        # Prevents double-click / network retry duplication
        from datetime import timedelta
        recent_order = Order.objects.filter(
            customer=self.user, 
            created_at__gte=timezone.now() - timedelta(seconds=30),
            status='pending'
        ).first()
        if recent_order:
            return None, None, "Order already in progress. Please wait."

        # 4. Create order in safe transaction
        try:
            with transaction.atomic():

                # A. Lock inventory
                # We strictly use the Cart for checkout to ensure DB locking works correctly.
                cart_items = list(cart.items.select_for_update().select_related('sku'))
                cart_items.sort(key=lambda x: x.sku.id)

                for item in cart_items:
                    try:
                        check_and_lock_inventory(warehouse.id, item.sku.id, item.quantity)
                    except ValueError as e:
                        return None, None, f"Out of Stock: {item.sku.name} ({str(e)})"

                # B. Create Order
                order = Order.objects.create(
                    customer=self.user,
                    warehouse=warehouse,
                    delivery_address_json=self.delivery_address,
                    delivery_city=self.delivery_address.get('city'),
                    delivery_pincode=self.delivery_address.get('pincode'),
                    delivery_lat=self.lat,
                    delivery_lng=self.lng,
                    status='pending',
                    payment_status='pending',
                )

                # C. Create Order Items
                items_to_create = []
                for item in cart_items:
                    unit_price = item.sku.sale_price or Decimal("0.00")
                    items_to_create.append(OrderItem(
                        order=order,
                        sku=item.sku,
                        quantity=item.quantity,
                        unit_price=unit_price,
                        total_price=unit_price * item.quantity,
                        sku_name_snapshot=item.sku.name
                    ))

                OrderItem.objects.bulk_create(items_to_create)

                # D. Compute totals
                order.recalculate_totals(save=True)
                
                # E. Clear Cart
                cart.items.all().delete()

                # F. Payment
                payment_data = None

                if self.payment_method == "COD":
                    Payment.objects.create(
                        order=order,
                        user=self.user,
                        payment_method=Payment.PaymentMethod.COD,
                        amount=order.final_amount,
                        status=Payment.PaymentStatus.PENDING
                    )
                    payment_data = {"mode": "COD", "status": "PENDING"}

                elif self.payment_method == "RAZORPAY":
                    try:
                        if order.final_amount > 0:
                            rzp_id = create_razorpay_order(order, order.final_amount)
                            Payment.objects.create(
                                order=order,
                                user=self.user,
                                amount=order.final_amount,
                                payment_method=Payment.PaymentMethod.RAZORPAY,
                                gateway_order_id=rzp_id,
                            )
                            order.payment_gateway_order_id = rzp_id
                            order.save(update_fields=["payment_gateway_order_id"])
                            payment_data = {
                                "mode": "RAZORPAY",
                                "razorpay_order_id": rzp_id,
                                "amount": str(order.final_amount),
                                "currency": "INR"
                            }
                        else:
                            payment_data = {"mode": "FREE", "status": "SUCCESS"}
                            order.payment_status = "paid"
                            order.save()
                    except Exception as e:
                        logger.error(f"Razorpay error: {e}")
                        raise ValueError("Payment gateway error. Try COD.")

                return order, payment_data, None

        except ValueError as ve:
            return None, None, str(ve)
        except Exception as e:
            logger.exception("Fatal checkout failure")
            return None, None, "Internal checkout error."

# apps/orders/services.py

def cancel_order(order, cancelled_by=None, reason=""):
    from .models import OrderTimeline, OrderCancellation
    from apps.inventory.models import InventoryStock
    from apps.warehouse.models import PickingTask, BinInventory
    from django.db.models import F
    
    try:
        with transaction.atomic():
            # RELOAD with lock
            locked_order = Order.objects.select_for_update().get(id=order.id)
            
            if locked_order.status in ['cancelled', 'delivered']:
                return False, 'Cannot cancel order in its current state.'
                
            locked_order.status = 'cancelled'
            locked_order.cancelled_at = timezone.now()
            locked_order.save(update_fields=['status', 'cancelled_at'])
            
            # FIX: Restore Physical Stock (BinInventory)
            # Find associated Picking Tasks
            picking_tasks = PickingTask.objects.filter(order_id=str(locked_order.id))
            
            for pt in picking_tasks:
                for pick_item in pt.items.all():
                    # If item was reserved/picked, we must release reservation on the Bin
                    # Note: Ideally we move to a 'Returns' bin if already packed, 
                    # but for immediate fix, we release the 'reserved_qty' on the original bin
                    # assuming it hasn't left the warehouse physically yet.
                    
                    bin_inv = BinInventory.objects.select_for_update().get(
                        bin=pick_item.bin, 
                        sku=pick_item.sku
                    )
                    
                    # Logic: 
                    # If picked_qty > 0, it means it was moved from Bin -> Packer. 
                    # We assume Packer puts it back (Operational procedure).
                    # We just need to ensure the Bin record allows it.
                    
                    # Release reservation equal to what was asked to pick
                    bin_inv.reserved_qty = max(0, bin_inv.reserved_qty - pick_item.qty_to_pick)
                    bin_inv.save()

                # Cancel the task
                pt.status = 'CANCELLED'
                pt.save()

            # Restore Logical Stock (InventoryStock)
            for item in locked_order.items.all():
                InventoryStock.objects.filter(
                    warehouse=locked_order.warehouse,
                    sku=item.sku
                ).update(
                    available_qty=F('available_qty') + item.quantity,
                    # We only reduce reserved if we haven't already reconciled it elsewhere.
                    # Given the flow, we assume the reservation is held until cancellation.
                    reserved_qty=F('reserved_qty') - item.quantity
                )

            OrderTimeline.objects.create(order=locked_order, status='cancelled', notes=reason)
            OrderCancellation.objects.create(order=locked_order, reason=reason, cancelled_by=cancelled_by or 'OPS')
            
            if locked_order.payment_status == 'paid':
                from apps.orders.signals import order_refund_requested
                transaction.on_commit(lambda: order_refund_requested.send(
                    sender=Order, order_id=locked_order.id, amount=locked_order.final_amount, reason=reason
                ))
        return True, None
    except Exception as e:
        logger.exception("Cancel order failed")
        return False, str(e)


def get_nearest_warehouse(lat, lng):
    radius = getattr(settings, 'DELIVERY_RADIUS_KM', 15.0)
    try:
        pnt = Point(float(lng), float(lat), srid=4326)
        wh = Warehouse.objects.filter(
            is_active=True,
            location__distance_lte=(pnt, D(km=radius))
        ).annotate(
            distance=Distance('location', pnt)
        ).order_by('distance').first()
        return wh, wh.distance.km if wh else None
    except Exception as e:
        logger.error(f"Geo lookup error: {e}")
        return None, None

def process_successful_payment(order):
    try:
        with transaction.atomic():
            # Refresh from DB to get lock/latest state
            order = Order.objects.select_for_update().get(id=order.id)
            if order.status != 'pending' or order.payment_status == 'paid':
                return True, "Already processed"
            
            order.status = "confirmed"
            order.payment_status = "paid"
            order.confirmed_at = timezone.now()
            order.save(update_fields=["status", "payment_status", "confirmed_at"])

            payment = order.payments.first()
            if payment:
                payment.status = Payment.PaymentStatus.SUCCESSFUL
                payment.save(update_fields=["status"])

            # WMS Signal
            wms_items = [{"sku_id": str(i.sku_id), "qty": i.quantity} for i in order.items.all()]
            
            # Use on_commit to ensure signal sends only after DB commit
            transaction.on_commit(lambda: send_order_created.send(
                sender=Order,
                order_id=order.id,
                customer_id=order.customer.id,
                order_items=wms_items,
                metadata={"warehouse_id": str(order.warehouse_id)}
            ))
            return True, "Success"
    except Exception as e:
        logger.exception("Payment process failed")
        return False, str(e)


