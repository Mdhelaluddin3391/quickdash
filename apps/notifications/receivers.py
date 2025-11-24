# apps/notifications/receivers.py
import logging

from django.dispatch import receiver

from apps.orders.signals import send_order_created, order_refund_requested
from apps.warehouse.signals import dispatch_ready_for_delivery
from apps.delivery.signals import delivery_completed
from .services import notify_user

logger = logging.getLogger(__name__)


@receiver(send_order_created)
def handle_order_created_notification(
    sender,
    order_id,
    customer_id,
    **kwargs,
):
    """
    Order create hone pe customer ko push/SMS.
    """
    from apps.orders.models import Order
    from django.contrib.auth import get_user_model

    User = get_user_model()

    try:
        order = Order.objects.get(id=order_id)
        customer = User.objects.get(id=customer_id)
    except (Order.DoesNotExist, User.DoesNotExist):
        logger.exception("Order or user not found for order_created notification")
        return

    context = {
        "order_id": str(order.id),
        "amount": str(order.final_amount),
    }
    notify_user(
        user=customer,
        event_key="order_created_customer",
        context=context,
        template_fallback_title="Order placed successfully",
        template_fallback_body="Your order ${order_id} has been placed. Amount: ₹${amount}",
    )


@receiver(dispatch_ready_for_delivery)
def handle_order_out_for_delivery(
    sender,
    dispatch_id,
    order_id,
    warehouse_id,
    pickup_otp,
    **kwargs,
):
    """
    WMS se signal: order out for delivery -> customer notification.
    """
    from apps.orders.models import Order

    try:
        order = Order.objects.get(id=order_id)
        customer = order.customer
    except Order.DoesNotExist:
        logger.exception("Order %s not found for out_for_delivery notification", order_id)
        return

    context = {
        "order_id": str(order.id),
    }
    notify_user(
        user=customer,
        event_key="order_out_for_delivery",
        context=context,
        template_fallback_title="Order out for delivery",
        template_fallback_body="Your order ${order_id} is out for delivery.",
    )


@receiver(delivery_completed)
def handle_delivery_completed(
    sender,
    order,
    rider_code,
    **kwargs,
):
    """
    Delivery module se: order delivered -> customer notification.
    """
    customer = order.customer
    context = {
        "order_id": str(order.id),
        "rider_code": rider_code,
    }
    notify_user(
        user=customer,
        event_key="order_delivered_customer",
        context=context,
        template_fallback_title="Order delivered",
        template_fallback_body="Your order ${order_id} has been delivered.",
    )


@receiver(order_refund_requested)
def handle_order_refund_requested(
    sender,
    order_id,
    amount,
    reason,
    **kwargs,
):
    """
    Orders: refund request -> customer notification.
    """
    from apps.orders.models import Order

    try:
        order = Order.objects.get(id=order_id)
        customer = order.customer
    except Order.DoesNotExist:
        logger.exception("Order %s not found for refund notification", order_id)
        return

    context = {
        "order_id": str(order.id),
        "amount": str(amount),
        "reason": reason or "",
    }
    notify_user(
        user=customer,
        event_key="order_refund_requested",
        context=context,
        template_fallback_title="Refund initiated",
        template_fallback_body="Refund of ₹${amount} initiated for order ${order_id}. ${reason}",
    )
