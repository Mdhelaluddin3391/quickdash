# apps/utils/tests.py
from django.test import TestCase
from rest_framework.exceptions import ValidationError
from .validators import validate_phone, validate_lat_lng

class ValidatorTests(TestCase):
    def test_phone_validator(self):
        self.assertEqual(validate_phone("+919876543210"), "+919876543210")
        with self.assertRaises(ValidationError):
            validate_phone("123")  # Invalid

    def test_lat_lng_validator(self):
        # Valid coordinates
        validate_lat_lng(12.9716, 77.5946)
        
        # Invalid Latitude
        with self.assertRaises(ValueError):
            validate_lat_lng(91.0, 77.5946)
            
        # Invalid Longitude
        with self.assertRaises(ValueError):
            validate_lat_lng(12.9716, 181.0)