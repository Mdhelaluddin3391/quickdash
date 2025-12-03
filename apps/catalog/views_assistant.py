# apps/catalog/views_assistant.py
import re
from decimal import Decimal
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.db.models import Q, Sum
from apps.catalog.models import SKU, FlashSale
from apps.orders.models import Cart, CartItem

class ShoppingAssistantView(APIView):
    """
    AI Salesman Bot 🤖
    - Suggests products
    - Upsells based on Cart Value
    - Auto-adds Free Gifts (Inventory managed)
    """
    permission_classes = [AllowAny]

    def post(self, request):
        message = request.data.get('message', '').lower().strip()
        user = request.user if request.user.is_authenticated else None
        
        # --- 1. CONFIGURATION (Offer Rules) ---
        FREE_GIFT_THRESHOLD = 200
        FREE_GIFT_SKU_CODE = "VEG-CORIANDER"  # Ensure this SKU exists in DB
        
        # Helper: Get Current Cart Total
        current_total = 0
        cart = None
        if user:
            cart, _ = Cart.objects.get_or_create(customer=user)
            current_total = cart.items.aggregate(t=Sum('total_price'))['t'] or 0

        # --- 2. GREETING & UPSELL ---
        if not message or message in ['start', 'hi', 'hello']:
            reply = (
                "Namaste! 🙏 Main aapka QuickDash Salesman hu.\n\n"
                "Aaj market main **Taaza Sabzi** aur **Grocery** pe bhari chhoot hai!\n"
                f"💡 **Offer:** ₹{FREE_GIFT_THRESHOLD} ki shopping kijiye aur **Fresh Dhaniya FREE** paiye!\n\n"
                "Bataiye, aaj ghar ke liye kya bheju? (Jaise: '5kg Aloo', '2 packet Milk')"
            )
            return Response({"reply": reply})

        # --- 3. SHOW DEALS ---
        if any(x in message for x in ['offer', 'deal', 'kya hai', 'dikhao']):
            sales = FlashSale.objects.filter(is_active=True)[:3]
            if sales:
                suggestions = [f"🔥 {s.sku.name} sirf ₹{int(s.discounted_price)} mein!" for s in sales]
                return Response({"reply": "Sir/Ma'am, yeh items abhi garam bik rahe hain:\n" + "\n".join(suggestions) + "\n\nKya add karu?"})
            return Response({"reply": "Sabhi items par best rate hai! Aap bas item ka naam bataiye."})

        # --- 4. PARSE ORDER (Item + Qty) ---
        # Regex to find quantity (e.g., "5 kg", "2 packet", or just "5")
        qty_match = re.search(r'(\d+)', message)
        quantity = int(qty_match.group(1)) if qty_match else None
        
        # Clean message to find Product Name
        clean_text = re.sub(r'(\d+)|kg|gm|packet|pcs|pack|chahiye|bhejo|add|i want', '', message).strip()
        
        if not clean_text:
            return Response({"reply": "Maaf kijiye, kaunsa item chahiye? (Likhein: '2 kg Onion')"})

        # Database Search
        sku = SKU.objects.filter(
            Q(name__icontains=clean_text) | 
            Q(search_keywords__icontains=clean_text),
            is_active=True
        ).first()

        if not sku:
            return Response({"reply": f"Arre! '{clean_text}' abhi stock main nahi dikh raha. Kuch aur try karein? (Jaise: Rice, Oil, Tomato)"})

        # --- 5. ADD TO CART LOGIC ---
        if quantity:
            if not user:
                return Response({"reply": f"Ji main {sku.name} add toh kardu, par pehle aap **Login** kar lijiye taaki list save rahe."})
            
            # Add Item
            item, created = CartItem.objects.get_or_create(cart=cart, sku=sku, defaults={'quantity': 0})
            item.quantity += quantity
            # Ensure normal price
            item.unit_price = sku.sale_price 
            item.save()
            
            # Recalculate Total
            new_total = cart.items.aggregate(t=Sum('total_price'))['t'] or 0
            
            # --- 6. THE SALESMAN UPSELL LOGIC ---
            response_msg = f"✅ Badhiya choice! {quantity} {sku.unit} **{sku.name}** add kar diya."
            
            # Check Free Gift Logic
            if new_total >= FREE_GIFT_THRESHOLD:
                # Check if gift already added
                gift_sku = SKU.objects.filter(sku_code=FREE_GIFT_SKU_CODE).first()
                if gift_sku:
                    gift_item, gift_created = CartItem.objects.get_or_create(
                        cart=cart, 
                        sku=gift_sku, 
                        defaults={'quantity': 1, 'unit_price': Decimal("0.00")}
                    )
                    if gift_created:
                         # Explicitly set price to 0 for free item
                        gift_item.unit_price = Decimal("0.00")
                        gift_item.save()
                        response_msg += f"\n\n🎉 **Mubarak ho!** Aapka total ₹{new_total} ho gaya hai. **{gift_sku.name} (Free)** add kar diya hai!"
                    else:
                        response_msg += f"\n(Total: ₹{new_total}. Free gift already added!)"
            else:
                short_amt = FREE_GIFT_THRESHOLD - new_total
                response_msg += f"\n\n💰 Total: ₹{new_total}. Bas **₹{short_amt}** ka aur le lijiye, **Dhaniya FREE** milega! Kuch Fruits du?"

            return Response({
                "reply": response_msg,
                "action": "cart_updated"
            })

        else:
            # Quantity nahi batayi
            return Response({
                "reply": f"Ji **{sku.name}** mil gaya! Kitna bheju? (1, 2, 5...)",
                "context_sku_id": sku.id 
            })

    def put(self, request):
        """ Handle only quantity reply """
        sku_id = request.data.get('context_sku_id')
        quantity = request.data.get('quantity')
        user = request.user

        if not user or not user.is_authenticated:
             return Response({"reply": "Login required."})

        try:
            sku = SKU.objects.get(id=sku_id)
            cart, _ = Cart.objects.get_or_create(customer=user)
            item, created = CartItem.objects.get_or_create(cart=cart, sku=sku, defaults={'quantity': 0})
            item.quantity += int(quantity)
            item.save()
            
            # Check Total again for Salesman Dialogue
            new_total = cart.items.aggregate(t=Sum('total_price'))['t'] or 0
            msg = f"✅ {quantity} {sku.unit} {sku.name} add ho gaya.\nTotal ab ₹{new_total} hai."
            
            if new_total < 200:
                msg += f"\nThoda aur khareed lo sir, ₹200 hote hi gift pakka!"
            
            return Response({
                "reply": msg,
                "action": "cart_updated"
            })
        except Exception:
            return Response({"reply": "Kuch gadbad ho gayi. Phir se try karein."})