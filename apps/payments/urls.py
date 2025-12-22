from django.urls import path
from .views import PaymentSuccessView, RazorpayWebhookView

urlpatterns = [
    path('verify/', PaymentSuccessView.as_view(), name='payment-verify'),
    path('webhook/', RazorpayWebhookView.as_view(), name='payment-webhook'),
]