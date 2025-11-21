# apps/payments/urls.py
from django.urls import path

from .views import (
    CreatePaymentIntentAPIView,
    VerifyPaymentAPIView,
    RazorpayWebhookView,
)

urlpatterns = [
    path(
        "create-intent/",
        CreatePaymentIntentAPIView.as_view(),
        name="payment-create-intent",
    ),
    path(
        "verify/",
        VerifyPaymentAPIView.as_view(),
        name="payment-verify",
    ),
    path(
        "webhook/razorpay/",
        RazorpayWebhookView.as_view(),
        name="payment-webhook-razorpay",
    ),
]
