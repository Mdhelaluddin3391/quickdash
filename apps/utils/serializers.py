# apps/utils/serializers.py
from rest_framework import serializers


class KeyValueSerializer(serializers.Serializer):
    """
    Generic serializer for key/value pairs.
    Useful for:
    - simple config responses
    - status info
    - dynamic key/value APIs
    """
    key = serializers.CharField()
    value = serializers.CharField()


class HealthSerializer(serializers.Serializer):
    """
    Health check structured response.
    """
    status = serializers.CharField()
    db_status = serializers.CharField()
    timestamp = serializers.DateTimeField()


class ServerInfoSerializer(serializers.Serializer):
    """
    Used by ServerInfoView — reusable for info endpoints.
    """
    app_name = serializers.CharField()
    version = serializers.CharField()
    debug = serializers.BooleanField()
