# apps/orders/services.py
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from apps.warehouse.utils.warehouse_selector import select_best_warehouse  # <--- IMPORT THIS
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
    # GET WAREHOUSE (SMART ROUTING)
    # ---------------------------------------------
    def _get_warehouse(self):
        # 1. Cart Items Fetch Karein (Selector Logic ke liye)
        try:
            cart = Cart.objects.prefetch_related('items').get(customer=self.user)
            if not cart.items.exists():
                return None
            
            # Selector ko simple list chahiye: [{'sku_id': uuid, 'qty': 1}, ...]
            order_items_data = [
                {"sku_id": item.sku_id, "qty": item.quantity} 
                for item in cart.items.all()
            ]
        except Cart.DoesNotExist:
            return None

        # 2. Smart Selector Call Karein
        if self.lat and self.lng:
            try:
                # Ye function 10km limit aur stock check dono karega
                wh = select_best_warehouse(
                    order_items=order_items_data,
                    customer_location=(self.lat, self.lng)
                )
                if wh:
                    logger.info(f"[Smart Routing] Selected {wh.code} for User {self.user.id}")
                    return wh
            except Exception as e:
                logger.warning(f"[Smart Routing] Error: {e}")
                # Fallthrough to other checks if needed, or return None
                return None

        # 3. Fallback (Agar Manual ID bheja gaya ho - Testing ke liye)
        if self.warehouse_id:
            try:
                return Warehouse.objects.get(id=self.warehouse_id, is_active=True)
            except Warehouse.DoesNotExist:
                pass

        return None

    # ---------------------------------------------
    # EXECUTE CHECKOUT
    # ---------------------------------------------
    def execute(self):
        # 1. Idempotency Check
        idempotency_key = self.data.get("idempotency_key")
        if idempotency_key:
            existing_order = Order.objects.filter(metadata__idempotency_key=idempotency_key).first()
            if existing_order:
                payment_data = None
                if existing_order.payment_status != 'paid':
                    payment_data = {"status": existing_order.payment_status}
                return existing_order, payment_data, None

        # 2. Validate Warehouse (10km + Stock Check)
        warehouse = self._get_warehouse()
        
        # USER FRIENDLY MESSAGE
        if not warehouse:
            return None, None, "Maaf kijiye, ye items abhi aapke location (10km range) mein available nahi hain."

        # Pricing check...
        expected_total = self.data.get("expected_total")
        if expected_total is None:
             return None, None, "Pricing update required. Please refresh cart."

        try:
            with transaction.atomic():
                # ... (Baaki logic same rahega jo maine pehle diya tha - Cart Locking, Inventory, Order Creation) ...
                
                # ... (Cart Locking)
                try:
                    cart = Cart.objects.select_for_update().select_related('customer').get(customer=self.user)
                except Cart.DoesNotExist:
                    return None, None, "Cart not found."

                # Lock items
                cart_items = list(cart.items.select_for_update().select_related('sku'))
                cart_items.sort(key=lambda x: x.sku.id)

                # Inventory Reservation (Batch)
                from apps.inventory.services import batch_check_and_lock_inventory
                try:
                    batch_check_and_lock_inventory(warehouse.id, cart_items)
                except ValueError as e:
                    # Agar warehouse select hone ke baad bhi millisecond mein stock khatam ho gaya
                    return None, None, f"Out of Stock: {str(e)}"

                # Price Calculation
                total_check = Decimal("0.00")
                items_to_create = []
                
                for item in cart_items:
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

                if abs(total_check - Decimal(str(expected_total))) > Decimal("0.05"):
                    return None, None, "Prices have updated. Please review cart."

                # Order Create
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
                    final_amount=total_check,
                    metadata={"idempotency_key": idempotency_key} if idempotency_key else {}
                )

                for i in items_to_create:
                    i.order = order
                OrderItem.objects.bulk_create(items_to_create)
                cart.items.all().delete()

                # Payment Setup
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
                        except Exception:
                            raise ValueError("Payment gateway error.")
                    else:
                        payment_data = {"mode": "FREE", "status": "SUCCESS"}
                        order.payment_status = "paid"
                        order.save()

                return order, payment_data, None

        except ValueError as ve:
            return None, None, str(ve)
        except Exception as e:
            logger.exception("Checkout Fatal Error")
            return None, None, "Something went wrong. Please try again."


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