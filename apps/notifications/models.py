# apps/notifications/models.py
from django.db import models
from django.conf import settings

class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=255)
    message = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user} - {self.title}"


class FCMDevice(models.Model):
    """
    User ke mobile devices ke FCM tokens store karne ke liye.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="fcm_devices")
    fcm_token = models.CharField(max_length=255, unique=True) # Firebase Token
    device_type = models.CharField(max_length=20, default="android") # android/ios
    is_active = models.BooleanField(default=True)
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.device_type}"