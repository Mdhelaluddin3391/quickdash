import re
from rest_framework import serializers


def validate_phone(value):
    pattern = r"^\+?\d{10,15}$"
    if not re.match(pattern, str(value)):
        raise serializers.ValidationError("Invalid phone number format.")
    return value


def validate_lat_lng(lat, lng):
    if not (-90 <= lat <= 90):
        raise ValueError("Latitude must be between -90 and 90.")
    if not (-180 <= lng <= 180):
        raise ValueError("Longitude must be between -180 and 180.")
