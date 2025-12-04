# apps/catalog/views_assistant.py
import re
import random
from decimal import Decimal
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.db.models import Q, Sum, F
from django.contrib.postgres.search import TrigramSimilarity  # 👈 Smart Brain
from apps.catalog.models import SKU, Category, FlashSale
from apps.orders.models import Cart, CartItem

class ShoppingAssistantView(APIView):
    """
    LEVEL 2 AI Salesman Bot 🤖
    - Auto-corrects spelling mistakes (e.g., 'milkk' -> 'Milk')
    - Contextual Upselling (Bought Milk? -> Suggest Bread/Eggs)
    - Manages Cart & Free Gifts smartly
    """
    permission_classes = [AllowAny]

    def post(self, request):
        message = request.data.get('message', '').lower().strip()
        user = request.user if request.user.is_authenticated else None
        
        # --- 1. CART CONTEXT LOAD KAREIN ---
        cart = None
        current_total = 0
        if user:
            cart, _ = Cart.objects.get_or_create(customer=user)
            current_total = cart.items.aggregate(t=Sum('total_price'))['t'] or 0

        # --- 2. GREETING & SMART INTRO ---
        greetings = ['hi', 'hello', 'start', 'hey', 'namaste']
        if not message or message in greetings:
            return Response({
                "reply": self.get_smart_greeting(user, current_total)
            })

        # --- 3. SHOW OFFERS ---
        if any(x in message for x in ['offer', 'deal', 'sasta', 'discount']):
            return Response({"reply": self.get_flash_deals()})

        # --- 4. SMART PRODUCT PARSING (NLP Lite) ---
        # Quantity nikalo (e.g., "5 kg", "2 pkt", "10")
        qty_match = re.search(r'(\d+)', message)
        quantity = int(qty_match.group(1)) if qty_match else None
        
        # "Junk words" hatao taaki product ka naam mile
        stopwords = ['chahiye', 'bhejo', 'add', 'want', 'need', 'kg', 'gm', 'packet', 'pcs', 'pack', 'liter', 'ltr', 'kilo', 'please', 'do']
        clean_text = message
        for word in stopwords:
            clean_text = clean_text.replace(word, '')
        
        clean_text = clean_text.replace(str(quantity), '').strip() # Remove number too

        if len(clean_text) < 2 and not quantity:
            return Response({"reply": "Ji, main samjha nahi. Kya chahiye? (Likhein: 'Milk', 'Onion', 'Rice')"})

        # --- 5. FIND PRODUCT (SMART SEARCH) ---
        sku = self.find_best_match_product(clean_text)

        if not sku:
            return Response({"reply": f"🤔 Maaf kijiye, '{clean_text}' jaisa kuch nahi mila. Spelling check karein ya kuch aur try karein (e.g., Potato, Oil)."})

        # --- 6. ACTION: ADD TO CART or ASK QTY ---
        if quantity:
            if not user:
                return Response({"reply": f"Ji main **{sku.name}** add toh kardu, par pehle aap **Login** kar lijiye."})
            
            # Add Item
            item, created = CartItem.objects.get_or_create(cart=cart, sku=sku, defaults={'quantity': 0})
            item.quantity += quantity
            item.unit_price = sku.sale_price # Price refresh
            item.save()
            
            # Recalculate Total
            new_total = cart.items.aggregate(t=Sum('total_price'))['t'] or 0
            
            # --- 7. SMART UPSELL GENERATION ---
            upsell_msg = self.generate_upsell(sku, new_total)
            
            return Response({
                "reply": f"✅ Done! {quantity} {sku.unit} **{sku.name}** add ho gaya.\n\n{upsell_msg}",
                "action": "cart_updated"
            })

        else:
            # Product mila par quantity nahi pata
            return Response({
                "reply": f"Ji **{sku.name}** (₹{int(sku.sale_price)}/{sku.unit}) mil gaya! Kitna bheju? (Likhein: 1, 2, 5...)",
                "context_sku_id": sku.id 
            })

    def put(self, request):
        """ Follow-up: Jab user sirf quantity bole (e.g., '2') """
        sku_id = request.data.get('context_sku_id')
        quantity = request.data.get('quantity')
        user = request.user

        if not user or not user.is_authenticated:
             return Response({"reply": "Please login first."})

        try:
            sku = SKU.objects.get(id=sku_id)
            cart, _ = Cart.objects.get_or_create(customer=user)
            item, created = CartItem.objects.get_or_create(cart=cart, sku=sku, defaults={'quantity': 0})
            item.quantity += int(quantity)
            item.save()
            
            new_total = cart.items.aggregate(t=Sum('total_price'))['t'] or 0
            upsell_msg = self.generate_upsell(sku, new_total)
            
            return Response({
                "reply": f"✅ {quantity} {sku.unit} **{sku.name}** bag mein daal diya.\n\n{upsell_msg}",
                "action": "cart_updated"
            })
        except Exception:
            return Response({"reply": "Kuch gadbad ho gayi. Phir se try karein."})

    # --- HELPER BRAINS 🧠 ---

    def find_best_match_product(self, query):
        """ 
        Uses Postgres Trigram Similarity to find products even with typos.
        Matches: 'Aple' -> 'Apple', 'Onoin' -> 'Onion'
        """
        try:
            return SKU.objects.annotate(
                similarity=TrigramSimilarity('name', query)
            ).filter(
                Q(similarity__gt=0.1) | Q(name__icontains=query) | Q(search_keywords__icontains=query),
                is_active=True
            ).order_by('-similarity').first()
        except Exception:
            # Fallback for SQLite (Dev mode without Postgres extensions)
            return SKU.objects.filter(name__icontains=query, is_active=True).first()

    def get_smart_greeting(self, user, total):
        """ Greeting based on Cart Status """
        name = user.full_name.split(' ')[0] if user and user.full_name else "Sir/Ma'am"
        
        if total > 0:
            return f"Welcome back {name}! 🛒 Aapki cart mein ₹{total} ka saaman hai.\nAur kya chahiye? (Type: 'Milk', 'Bread')."
        
        return (
            f"Namaste {name}! 🙏 Main QuickDash Assistant hu.\n"
            "Aaj **Sabzi** aur **Grocery** taaza aayi hai.\n"
            "Bataiye ghar ke liye kya bheju? (Jaise: '5kg Aloo', '2 packet Milk')"
        )

    def get_flash_deals(self):
        sales = FlashSale.objects.filter(is_active=True)[:3]
        if sales:
            deals = [f"🔥 **{s.sku.name}** sirf ₹{int(s.discounted_price)}!" for s in sales]
            return "Aaj ke Hot Deals:\n" + "\n".join(deals) + "\n\nKaunsa add karu?"
        return "Abhi sabhi items par best rate hai! Aap bas order kijiye."

    def generate_upsell(self, current_sku, total_amt):
        """ 
        Suggests related items based on what was just added. 
        Uses Category to find siblings.
        """
        # 1. Free Gift Logic
        FREE_THRESHOLD = 499
        if total_amt >= FREE_THRESHOLD:
             return f"🎉 **Badhai ho!** Total ₹{total_amt} ho gaya. Delivery FREE rahegi!"
        
        # 2. Category Based Suggestion
        # Agar 'Milk' liya, toh 'Bread' ya 'Eggs' suggest karo
        if current_sku.category:
            related = SKU.objects.filter(
                category=current_sku.category, 
                is_active=True
            ).exclude(id=current_sku.id).order_by('?').first()
            
            if related:
                return f"💡 Saath mein **{related.name}** (₹{int(related.sale_price)}) bhi bheju? Log aksar saath lete hain."

        # 3. Generic Upsell
        short_amt = FREE_THRESHOLD - total_amt
        return f"💰 Total: ₹{total_amt}. Bas **₹{short_amt}** aur shop karein free delivery ke liye!"