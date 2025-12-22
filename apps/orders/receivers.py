from django.dispatch import receiver
from .signals import order_created, order_status_changed
# from apps.notifications.services import NotificationService (Example)

@receiver(order_created)
def notify_user_on_creation(sender, order, **kwargs):
    # NotificationService.send_sms(order.user, f"Order {order.order_id} placed.")
    pass

@receiver(order_status_changed)
def log_analytics(sender, order, old_status, new_status, **kwargs):
    # AnalyticsService.track_event("order_status_change", ...)
    pass