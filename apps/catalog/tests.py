# apps/catalog/tests.py
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from .models import Category, Brand, SKU

User = get_user_model()


class CategoryModelTests(TestCase):
    def test_category_slug_auto_generated_and_unique(self):
        parent = Category.objects.create(name="Dairy")
        c1 = Category.objects.create(name="Milk", parent=parent)
        c2 = Category.objects.create(name="Milk", parent=parent)

        self.assertNotEqual(c1.slug, c2.slug)
        self.assertTrue(c1.slug.startswith("milk"))
        self.assertTrue(c2.slug.startswith("milk"))


class SKUViewSetTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user(
            phone="+911111111111",
            password="testpass",
            is_staff=True,
        )
        self.normal = User.objects.create_user(
            phone="+922222222222",
            password="testpass",
        )

        self.cat = Category.objects.create(name="Dairy", is_active=True)
        self.brand = Brand.objects.create(name="Amul", is_active=True)

        self.active_sku = SKU.objects.create(
            sku_code="MILK-1L-AMUL",
            name="Amul Milk 1L",
            category=self.cat,
            brand=self.brand,
            sale_price="60.00",
            cost_price="50.00",
            is_active=True,
        )
        self.inactive_sku = SKU.objects.create(
            sku_code="OLD-MILK",
            name="Old Milk",
            category=self.cat,
            brand=self.brand,
            sale_price="40.00",
            cost_price="30.00",
            is_active=False,
        )

    def test_public_list_only_active_skus(self):
        url = reverse("sku-list")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        codes = [item["sku_code"] for item in resp.data]
        self.assertIn(self.active_sku.sku_code, codes)
        self.assertNotIn(self.inactive_sku.sku_code, codes)

    def test_staff_can_see_inactive_skus(self):
        self.client.force_authenticate(self.staff)
        url = reverse("sku-list")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        codes = [item["sku_code"] for item in resp.data]
        self.assertIn(self.active_sku.sku_code, codes)
        self.assertIn(self.inactive_sku.sku_code, codes)

    def test_get_sku_by_sku_code(self):
        url = reverse("sku-detail", kwargs={"sku_code": self.active_sku.sku_code})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["sku_code"], self.active_sku.sku_code)
