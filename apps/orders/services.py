# apps/orders/services.py
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D

from apps.warehouse.utils.warehouse_selector import select_best_warehouse
from apps.orders.models import Order, OrderItem, Cart
from apps.payments.models import Payment
from apps.warehouse.models import Warehouse, PickingTask, BinInventory
from apps.inventory.models import InventoryStock
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
        
        # Explicit items from "Buy Now" or similar flows
        self.direct_items = data.get("items") 

    # ---------------------------------------------
    # GET WAREHOUSE (SMART ROUTING)
    # ---------------------------------------------
    def _get_warehouse(self):
        order_items_data = []

        # 1. Source: Direct Items (Priority)
        if self.direct_items:
            # Serializer already validated structure
            order_items_data = [
                {"sku_id": item["sku_id"], "qty": item["quantity"]}
                for item in self.direct_items
            ]
        
        # 2. Source: Cart (Fallback)
        else:
            try:
                cart = Cart.objects.prefetch_related('items').get(customer=self.user)
                if cart.items.exists():
                    order_items_data = [
                        {"sku_id": item.sku_id, "qty": item.quantity} 
                        for item in cart.items.all()
                    ]
            except Cart.DoesNotExist:
                pass

        if not order_items_data:
            logger.warning(f"Checkout initiated with no items. User: {self.user.id}")
            return None

        # 3. Smart Selector Call
        if self.lat and self.lng:
            try:
                wh = select_best_warehouse(
                    order_items=order_items_data,
                    customer_location=(self.lat, self.lng)
                )
                if wh:
                    logger.info(f"[Smart Routing] Selected {wh.code} for User {self.user.id}")
                    return wh
            except Exception as e:
                logger.error(f"[Smart Routing] Error: {e}", exc_info=True)

        # 4. Fallback (Manual ID - e.g., Testing or specific store selection)
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

        # 2. Validate Warehouse
        warehouse = self._get_warehouse()
        if not warehouse:
            return None, None, "We could not find a warehouse with stock available in your area (10km)."

        # Pricing check
        expected_total = self.data.get("expected_total")
        if expected_total is None:
             return None, None, "Pricing update required. Please refresh."

        try:
            with transaction.atomic():
                # 3. Resolve Items (Cart vs Direct)
                items_to_process = []
                cart = None

                if self.direct_items:
                    # Fetch SKU objects for direct items
                    from apps.catalog.models import SKU
                    sku_ids = [item['sku_id'] for item in self.direct_items]
                    # Lock SKUs to prevent concurrent price changes
                    skus = {str(s.id): s for s in SKU.objects.filter(id__in=sku_ids).select_for_update()}
                    
                    for item in self.direct_items:
                        sku_obj = skus.get(str(item['sku_id']))
                        if not sku_obj:
                             raise ValueError(f"Invalid SKU ID: {item['sku_id']}")
                        items_to_process.append({
                            'sku': sku_obj,
                            'quantity': item['quantity']
                        })
                else:
                    # Lock Cart
                    try:
                        cart = Cart.objects.select_for_update().select_related('customer').get(customer=self.user)
                        cart_items_qs = cart.items.select_for_update().select_related('sku')
                        for ci in cart_items_qs:
                            items_to_process.append({
                                'sku': ci.sku,
                                'quantity': ci.quantity
                            })
                    except Cart.DoesNotExist:
                        return None, None, "Cart not found."

                if not items_to_process:
                     return None, None, "No items to checkout."

                # 4. Inventory Reservation (Batch)
                from apps.inventory.services import batch_check_and_lock_inventory
                try:
                    # Prepare list for locking service
                    lock_request = [
                        {'sku': i['sku'], 'quantity': i['quantity']} 
                        for i in items_to_process
                    ]
                    batch_check_and_lock_inventory(warehouse.id, lock_request)
                except ValueError as e:
                    return None, None, f"Out of Stock: {str(e)}"

                # 5. Price Calculation & Order Item Creation
                total_check = Decimal("0.00")
                order_items_db = []
                
                for item in items_to_process:
                    sku = item['sku']
                    qty = item['quantity']
                    current_unit_price = sku.sale_price or Decimal("0.00")
                    line_total = current_unit_price * qty
                    total_check += line_total
                    
                    order_items_db.append(OrderItem(
                        sku=sku,
                        quantity=qty,
                        unit_price=current_unit_price,
                        total_price=line_total,
                        sku_name_snapshot=sku.name
                    ))

                # Tolerance for float/decimal mismatches
                if abs(total_check - Decimal(str(expected_total))) > Decimal("0.05"):
                    return None, None, "Prices have updated. Please review."

                # 6. Create Order
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

                for i in order_items_db:
                    i.order = order
                OrderItem.objects.bulk_create(order_items_db)

                # Clear cart ONLY if we used it
                if cart:
                    cart.items.all().delete()

                # 7. Payment Setup
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
                                "amount": str(int(order.final_amount * 100)),
                                "currency": "INR",
                                "key_id": settings.RAZORPAY_KEY_ID
                            }
                        except Exception as e:
                            logger.error(f"Razorpay Error: {e}")
                            raise ValueError("Payment gateway initialization failed.")
                    else:
                        # 100% Discount / Free Order
                        payment_data = {"mode": "FREE", "status": "SUCCESS"}
                        order.payment_status = "paid"
                        order.save()

                return order, payment_data, None

        except ValueError as ve:
            return None, None, str(ve)
        except Exception as e:
            logger.exception("Checkout Fatal Error")
            return None, None, "Something went wrong. Please try again."

# Helper functions (process_successful_payment, cancel_order, get_nearest_warehouse) 
# kept as is from your original file, but assumed imported correctly.
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

def cancel_order(order, cancelled_by=None, reason=""):
    from apps.orders.models import OrderTimeline, OrderCancellation
    from django.db.models import F
    
    try:
        with transaction.atomic():
            locked_order = Order.objects.select_for_update().get(id=order.id)
            
            if locked_order.status in ['cancelled', 'delivered']:
                return False, 'Cannot cancel order in its current state.'
                
            locked_order.status = 'cancelled'
            locked_order.cancelled_at = timezone.now()
            locked_order.save(update_fields=['status', 'cancelled_at'])
            
            # 1. Restore Physical Stock (BinInventory) via Picking Tasks
            picking_tasks = PickingTask.objects.filter(order_id=str(locked_order.id))
            for pt in picking_tasks:
                for pick_item in pt.items.all():
                    bin_inv = BinInventory.objects.select_for_update().get(
                        bin=pick_item.bin, 
                        sku=pick_item.sku
                    )
                    bin_inv.reserved_qty = max(0, bin_inv.reserved_qty - pick_item.qty_to_pick)
                    bin_inv.save()
                pt.status = 'CANCELLED'
                pt.save()

            # 2. Restore Logical Stock (InventoryStock)
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