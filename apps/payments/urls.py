# apps/payments/urls.py
from django.urls import path
from .views import (
    CreatePaymentIntentAPIView,
    VerifyPaymentAPIView,
)

urlpatterns = [
    # Step 1: Customer se order ID lekar Razorpay link banana
    # POST /api/v1/payments/create-intent/
    path('create-intent/', CreatePaymentIntentAPIView.as_view(), name='payment-create-intent'),
    
    # Step 2: Payment complete hone ke baad Razorpay se verify karna
    # POST /api/v1/payments/verify/
    path('verify/', VerifyPaymentAPIView.as_view(), name='payment-verify'),
]