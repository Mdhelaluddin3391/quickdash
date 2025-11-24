# apps/notifications/tests.py
from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import NotificationTemplate, Notification, NotificationChannel
from .services import notify_user


User = get_user_model()


class NotificationServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone="+911234567890",
            password="testpass",
        )

        self.template = NotificationTemplate.objects.create(
            key="test_event",
            channel=NotificationChannel.PUSH,
            title_template="Hello ${name}",
            body_template="Hi ${name}, order ${order_id} created.",
        )

    def test_notify_user_creates_notification(self):
        notif = notify_user(
            user=self.user,
            event_key="test_event",
            context={"name": "Helal", "order_id": "OD123"},
        )

        self.assertIsNotNone(notif)
        self.assertEqual(notif.user, self.user)
        self.assertIn("Helal", notif.body)
        self.assertEqual(notif.channel, NotificationChannel.PUSH)

        count = Notification.objects.filter(user=self.user).count()
        self.assertEqual(count, 1)
