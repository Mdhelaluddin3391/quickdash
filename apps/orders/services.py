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
    def execute(self):
        # 1. Idempotency Check (Prevent Zombie Orders)
        idempotency_key = self.data.get("idempotency_key")
        if idempotency_key:
            existing_order = Order.objects.filter(metadata__idempotency_key=idempotency_key).first()
            if existing_order:
                # Return existing order state without re-executing logic
                payment_data = None
                if existing_order.payment_status != 'paid':
                    # Re-construct payment data if needed, or return generic pending status
                    payment_data = {"status": existing_order.payment_status}
                return existing_order, payment_data, None

        # 2. Validate warehouse (Geo-Logic Trust)
        warehouse = self._get_warehouse()
        if not warehouse:
            return None, None, "No serviceable warehouse found for this location."

        expected_total = self.data.get("expected_total")
        if expected_total is None:
             # Strict enforcement: Frontend MUST send what user saw
             return None, None, "Pricing version mismatch. Please refresh."

        try:
            with transaction.atomic():
                # 3. Aggressive Cart Locking (Prevent Cart Mutation)
                # Lock the PARENT cart to prevent new items being added mid-transaction
                try:
                    cart = Cart.objects.select_for_update().select_related('customer').get(customer=self.user)
                except Cart.DoesNotExist:
                    return None, None, "Cart not found."

                if not cart.items.exists():
                    return None, None, "Cart is empty."

                # Lock items and Sort by SKU ID to prevent Deadlocks during inventory locking
                cart_items = list(cart.items.select_for_update().select_related('sku'))
                cart_items.sort(key=lambda x: x.sku.id)

                # 4. Inventory Reservation
                # Delegate to the batch locker for atomic inventory updates
                from apps.inventory.services import batch_check_and_lock_inventory
                try:
                    batch_check_and_lock_inventory(warehouse.id, cart_items)
                except ValueError as e:
                    return None, None, f"Inventory Error: {str(e)}"

                # 5. Price Re-Calculation & Integrity Check
                total_check = Decimal("0.00")
                items_to_create = []
                
                for item in cart_items:
                    # Always use current DB price, never trust the cart's stale price
                    current_unit_price = item.sku.sale_price or Decimal("0.00")
                    line_total = current_unit_price * item.quantity
                    total_check += line_total
                    
                    items_to_create.append(OrderItem(
                        sku=item.sku,
                        quantity=item.quantity,
                        unit_price=current_unit_price,
                        total_price=line_total,
                        sku_name_snapshot=item.sku.name
                    ))

                # 6. Price Slippage Guard
                # Allow a tiny epsilon for float math, though Decimal should be exact.
                # If DB price changed since user loaded page, ABORT.
                if abs(total_check - Decimal(str(expected_total))) > Decimal("0.05"):
                    return None, None, "Prices have changed since you viewed the cart. Please review and try again."

                # 7. Create Order
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
                    final_amount=total_check, # Explicitly save the verified amount
                    metadata={"idempotency_key": idempotency_key} if idempotency_key else {}
                )

                # Bulk create items with order reference
                for i in items_to_create:
                    i.order = order
                OrderItem.objects.bulk_create(items_to_create)

                # 8. Clear Cart
                cart.items.all().delete()

                # 9. Payment Orchestration
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
                    if order.final_amount > 0:
                        try:
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
                        except Exception as e:
                            logger.error(f"Razorpay error: {e}")
                            # Rollback the entire transaction if payment setup fails
                            raise ValueError("Payment gateway error. Please try again.")
                    else:
                        payment_data = {"mode": "FREE", "status": "SUCCESS"}
                        order.payment_status = "paid"
                        order.save()

                return order, payment_data, None

        except ValueError as ve:
            return None, None, str(ve)
        except Exception as e:
            logger.exception("Fatal checkout failure")
            return None, None, "Internal system error during checkout."


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
                    
                    bin_inv = BinInventory.objects.select_for_update().get(
                        bin=pick_item.bin, 
                        sku=pick_item.sku
                    )
                    
                    # Logic: Release reservation equal to what was asked to pick
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