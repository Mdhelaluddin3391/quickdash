# apps/notifications/serializers.py
from rest_framework import serializers
from .models import Notification

class NotificationSerializer(serializers.ModelSerializer):
    """
    Customer ko notifications ki list dene ke liye.
    """
    # User phone aur full_name ko read-only field ke roop mein dikhana
    user_phone = serializers.CharField(source='user.phone', read_only=True)

    class Meta:
        model = Notification
        fields = ['id', 'user', 'user_phone', 'title', 'message', 'sent_at', 'is_read']
        read_only_fields = ['user', 'user_phone', 'title', 'message', 'sent_at']