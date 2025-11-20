# apps/payments/services.py
import razorpay
from django.conf import settings

# Client Initialize
client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

def create_razorpay_order(amount, currency="INR"):
    """
    Order ID generate karta hai jo frontend par chahiye hota hai.
    Amount paise mein hona chahiye (100 INR = 10000 paise).
    """
    data = {
        "amount": int(amount * 100),
        "currency": currency,
        "payment_capture": 1 # Auto capture
    }
    order = client.order.create(data=data)
    return order['id']

def verify_payment_signature(params_dict):
    """
    Signature verify karta hai taaki koi fake payment na kar sake.
    """
    try:
        client.utility.verify_payment_signature(params_dict)
        return True
    except razorpay.errors.SignatureVerificationError:
        return False

def initiate_refund(payment_obj):
    """
    Agar order cancel ho, toh paise wapas bhejne ka logic.
    """
    if not payment_obj.transaction_id:
        return False, "No transaction ID found."
        
    try:
        # Razorpay Refund API call
        refund = client.payment.refund(payment_obj.transaction_id, {
            "amount": int(payment_obj.amount * 100),
            "speed": "normal"
        })
        
        # Update Local DB
        payment_obj.status = 'REFUNDED'
        payment_obj.gateway_response = refund
        payment_obj.save()
        
        return True, refund
    except Exception as e:
        return False, str(e)