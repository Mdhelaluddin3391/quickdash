# apps/customers/serializers.py

from rest_framework import serializers
from django.contrib.gis.geos import Point

from .models import Address


class AddressSerializer(serializers.ModelSerializer):
    lat = serializers.FloatField(write_only=True)
    lng = serializers.FloatField(write_only=True)

    class Meta:
        model = Address
        fields = [
            "id",
            "label",
            "address_line",
            "lat",
            "lng",
            "is_default",
        ]
        read_only_fields = ["id", "is_default"]

    def create(self, validated_data):
        lat = validated_data.pop("lat")
        lng = validated_data.pop("lng")
        validated_data["location"] = Point(lng, lat)
        return super().create(validated_data)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["lat"] = instance.location.y
        data["lng"] = instance.location.x
        return data
