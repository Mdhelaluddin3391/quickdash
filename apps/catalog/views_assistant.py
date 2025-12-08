# apps/catalog/views_assistant.py

import re
import logging
from decimal import Decimal
from django.db.models import Q, Sum
from django.contrib.postgres.search import TrigramSimilarity

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from apps.catalog.models import SKU, FlashSale
from apps.orders.models import Cart, CartItem

logger = logging.getLogger(__name__)


class ShoppingAssistantView(APIView):
    """
    Rule-Based Shopping Assistant (NO LLM)
    --------------------------------------------------------
    ✔ Pure English reply
    ✔ Add / remove items
    ✔ Show / clear cart
    ✔ Smart product search (handles spelling mistakes)
    ✔ COD Order Confirmation
    ❌ Rejects UPI orders
    ✔ Upsell + free delivery hint
    """

    permission_classes = [AllowAny]

    # ---------------------------------------------------------------------
    # INTENT WORD SETS
    # ---------------------------------------------------------------------

    GREET_WORDS = {"hi", "hello", "hey", "start", "help", "assistant"}
    HELP_WORDS = {"help", "how", "what can you do", "guide", "support"}

    SHOW_CART_WORDS = {"cart", "show cart", "my cart", "view cart"}
    CLEAR_CART_WORDS = {"clear cart", "empty cart", "reset cart"}

    REMOVE_WORDS = {"remove", "delete", "take out", "minus"}

    OFFER_WORDS = {"offer", "offers", "discount", "sale", "deal"}

    ORDER_WORDS = {
        "order", "place order", "checkout", "confirm order",
        "cod", "cash on delivery", "place the order",
        "complete my order", "buy now"
    }

    BLOCK_UPI_WORDS = {
        "upi", "pay", "google pay", "phonepe", "gpay", "online payment"
    }

    STOPWORDS = {
        "add", "send", "need", "want", "give", "please", "pkt",
        "kg", "g", "gram", "ltr", "ml", "packet", "pack"
    }

    # ---------------------------------------------------------------------
    # MAIN POST HANDLER
    # ---------------------------------------------------------------------

    def post(self, request):
        text_raw = request.data.get("message", "").strip()
        message = self._clean(text_raw)

        user = request.user if request.user.is_authenticated else None
        cart, cart_total = self._get_cart_and_total(user)

        # 1. GREETING
        if not message or self._contains(message, self.GREET_WORDS):
            return Response({"reply": self._get_greeting(user, cart_total)})

        # 2. HELP
        if self._contains(message, self.HELP_WORDS):
            return Response({"reply": self._help_text()})

        # 3. SHOW CART
        if self._contains(message, self.SHOW_CART_WORDS):
            return Response({"reply": self._show_cart(user, cart)})

        # 4. CLEAR CART
        if self._contains(message, self.CLEAR_CART_WORDS):
            return Response({"reply": self._clear_cart(user, cart)})

        # 5. OFFERS
        if self._contains(message, self.OFFER_WORDS):
            return Response({"reply": self._flash_deals()})

        # 6. BLOCK UPI
        if self._contains(message, self.BLOCK_UPI_WORDS):
            return Response({"reply": self._reject_upi_message()})

        # 7. ORDER REQUEST
        if self._contains(message, self.ORDER_WORDS):
            return Response(self._handle_order(user, cart))

        # 8. REMOVE ITEM
        if self._contains(message, self.REMOVE_WORDS):
            return Response({"reply": self._remove_item(message, user, cart)})

        # 9. ADD PRODUCT FLOW
        return Response(self._handle_add(message, user, cart, cart_total))

    # ---------------------------------------------------------------------
    # ORDER LOGIC (COD ONLY)
    # ---------------------------------------------------------------------

    def _handle_order(self, user, cart):
        if not user:
            return {"reply": "Please login before placing an order."}

        if not cart or not cart.items.exists():
            return {"reply": "Your cart is empty. Add items before placing an order."}

        total = cart.items.aggregate(t=Sum("total_price"))["t"] or Decimal("0.00")

        summary = []
        for item in cart.items.select_related("sku"):
            summary.append(
                f"- {item.quantity} × {item.sku.name} (₹{int(item.unit_price)}) = ₹{int(item.total_price)}"
            )
        summary_text = "\n".join(summary)

        return {
            "reply": (
                "✅ **Your COD Order Request Has Been Received!**\n\n"
                f"**Order Summary:**\n{summary_text}\n\n"
                f"**Amount to Pay on Delivery:** ₹{int(total)}\n\n"
                "Your order is being processed. You will receive updates soon. 🚚"
            ),
            "action": "order_cod_requested"
        }

    # ---------------------------------------------------------------------
    # ADD ITEM LOGIC
    # ---------------------------------------------------------------------

    def _handle_add(self, message, user, cart, cart_total):
        qty = self._extract_qty(message)
        product_text = self._extract_product(message, qty)

        if not product_text:
            return {"reply": "I could not understand. Please mention a product name."}

        sku = self._find_product(product_text)
        if not sku:
            return {"reply": f"Sorry, I couldn’t find anything matching '{product_text}'."}

        if qty and not user:
            return {"reply": "Please login before adding items to your cart."}

        if qty and user:
            item, _ = CartItem.objects.get_or_create(cart=cart, sku=sku, defaults={"quantity": 0})
            item.quantity += qty
            item.unit_price = sku.sale_price
            item.save()

            new_total = cart.items.aggregate(t=Sum("total_price"))["t"] or Decimal("0.00")
            upsell = self._upsell(sku, new_total)

            return {
                "reply": f"Added {qty} {sku.unit} of **{sku.name}**.\n\n{upsell}",
                "action": "cart_updated"
            }

        return {
            "reply": f"Found **{sku.name}** for ₹{int(sku.sale_price)}/{sku.unit}. How many units should I add?",
            "context_sku_id": str(sku.id)
        }

    # ---------------------------------------------------------------------
    # REMOVE ITEM
    # ---------------------------------------------------------------------

    def _remove_item(self, message, user, cart):
        if not user:
            return "Please login to modify your cart."

        text = self._strip_stopwords(message)
        sku = self._find_product(text)
        if not sku:
            return "I couldn't identify which product to remove."

        try:
            item = CartItem.objects.get(cart=cart, sku=sku)
        except CartItem.DoesNotExist:
            return f"**{sku.name}** is not in your cart."

        item.delete()
        return f"Removed **{sku.name}** from your cart."

    # ---------------------------------------------------------------------
    # CART FUNCTIONS
    # ---------------------------------------------------------------------

    def _show_cart(self, user, cart):
        if not user:
            return "Please login to view your cart."

        if not cart or not cart.items.exists():
            return "Your cart is currently empty."

        lines = ["**Your Cart:**\n"]
        total = 0

        for item in cart.items.select_related("sku"):
            total += item.total_price
            lines.append(f"- {item.quantity} × {item.sku.name} = ₹{int(item.total_price)}")

        lines.append(f"\n**Total:** ₹{int(total)}")

        return "\n".join(lines)

    def _clear_cart(self, user, cart):
        if not user:
            return "Please login to clear your cart."

        if not cart or not cart.items.exists():
            return "Your cart is already empty."

        cart.items.all().delete()
        return "Your cart has been cleared."

    # ---------------------------------------------------------------------
    # HELP, OFFERS, GREETING, UPI REJECTION
    # ---------------------------------------------------------------------

    def _reject_upi_message(self):
        return (
            "❌ UPI / online payments are currently unavailable.\n"
            "Please proceed with **Cash on Delivery (COD)**."
        )

    def _help_text(self):
        return (
            "**I can help you with:**\n"
            "- Adding items (e.g., 'add 2 milk')\n"
            "- Removing items (e.g., 'remove bread')\n"
            "- Showing cart (e.g., 'show cart')\n"
            "- Clearing cart\n"
            "- Viewing offers\n"
            "- Placing a COD order\n\n"
            "Just type what you need!"
        )

    def _flash_deals(self):
        sales = FlashSale.objects.filter(is_active=True)[:3]
        if not sales:
            return "No active offers right now."

        lines = ["🔥 **Today's Best Deals:**"]
        for s in sales:
            lines.append(f"- {s.sku.name}: ₹{int(s.discounted_price)}")

        return "\n".join(lines)

    def _get_greeting(self, user, total):
        if user:
            return f"Welcome back! Your cart total is ₹{int(total)}. What would you like to order?"

        return (
            "Hello! I’m the QuickDash Shopping Assistant.\n"
            "Tell me what you want — for example: '2 kg rice', 'add milk', 'show cart'."
        )

    # ---------------------------------------------------------------------
    # UTILITIES (Clean, Search, Qty, etc.)
    # ---------------------------------------------------------------------

    def _clean(self, text):
        text = text.lower()
        text = re.sub(r"[^a-zA-Z0-9\s]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _contains(self, msg, words):
        return any(w in msg for w in words)

    def _get_cart_and_total(self, user):
        if not user:
            return None, Decimal("0.00")
        cart, _ = Cart.objects.get_or_create(customer=user)
        total = cart.items.aggregate(t=Sum("total_price"))["t"] or Decimal("0.00")
        return cart, total

    def _extract_qty(self, msg):
        m = re.search(r"(\d+)", msg)
        return int(m.group(1)) if m else None

    def _strip_stopwords(self, text):
        words = text.split()
        filtered = [w for w in words if w not in self.STOPWORDS]
        return " ".join(filtered)

    def _extract_product(self, msg, qty):
        if qty:
            msg = msg.replace(str(qty), "")
        msg = self._strip_stopwords(msg)
        return msg.strip()

    def _find_product(self, query):
        try:
            return (
                SKU.objects.annotate(similarity=TrigramSimilarity("name", query))
                .filter(Q(similarity__gt=0.1) | Q(name__icontains=query))
                .order_by("-similarity")
                .first()
            )
        except (ValueError, Exception) as e:
            logger.warning(f"Trigram search failed, falling back to icontains: {e}")
            return SKU.objects.filter(name__icontains=query).first()

    # ---------------------------------------------------------------------
    # UPSELL LOGIC
    # ---------------------------------------------------------------------

    def _upsell(self, sku, total):
        FREE_LIMIT = 499

        if total >= FREE_LIMIT:
            return (
                f"🎉 Your total is ₹{int(total)}. You now qualify for **FREE Delivery**!"
            )

        remaining = FREE_LIMIT - total
        return (
            f"Your current total is ₹{int(total)}. Add items worth ₹{int(remaining)} "
            f"to get **FREE delivery**!"
        )




# # apps/catalog/views_assistant.py
# import requests
# import json
# from rest_framework.views import APIView
# from rest_framework.response import Response
# from rest_framework.permissions import AllowAny
# from django.contrib.postgres.search import TrigramSimilarity
# from django.db.models import Q
# from .models import SKU

# class ShoppingAssistantView(APIView):
#     """
#     LOCAL AI ASSISTANT (Ollama Powered)
#     - Free
#     - Secure (No Data Leak)
#     - Runs on localhost:11434
#     """
#     permission_classes = [AllowAny]

#     def post(self, request):
#         user_message = request.data.get('message', '').strip()
        
#         # 1. SMART SEARCH (Context dhundhne ke liye)
#         # Database se milta-julta products nikalo
#         matched_products = SKU.objects.annotate(
#             similarity=TrigramSimilarity('name', user_message)
#         ).filter(
#             Q(similarity__gt=0.1) | Q(name__icontains=user_message) | Q(category__name__icontains=user_message),
#             is_active=True
#         ).order_by('-similarity')[:10]  # Top 10 products

#         # 2. CONTEXT BANANA
#         inventory_text = "Available Inventory:\n"
#         if matched_products.exists():
#             for p in matched_products:
#                 inventory_text += f"- {p.name}: ₹{p.sale_price} ({p.unit})\n"
#         else:
#             inventory_text = "No direct matching products found via search."

#         # 3. PROMPT (AI ko instruction)
#         prompt = f"""
#         You are a helpful grocery shopping assistant for 'QuickDash'.
        
#         CONTEXT (Real-time Stock):
#         {inventory_text}
        
#         USER SAYS: "{user_message}"
        
#         INSTRUCTIONS:
#         1. Only suggest products listed in the CONTEXT above.
#         2. If the user asks for something not in the list, apologize politely.
#         3. Keep the answer short, friendly, and use Hinglish (Hindi+English mix).
#         4. Do not mention "I am an AI". Act like a shopkeeper.
#         """

#         # 4. CALL LOCAL OLLAMA API (Free & Secure)
#         try:
#             response = requests.post(
#                 "http://localhost:11434/api/generate",
#                 json={
#                     "model": "llama3",  # Ya "mistral" jo bhi install kiya ho
#                     "prompt": prompt,
#                     "stream": False
#                 },
#                 timeout=10
#             )
            
#             if response.status_code == 200:
#                 ai_reply = response.json().get("response", "Network error in AI.")
#             else:
#                 ai_reply = "System is busy. Please search manually."

#         except Exception as e:
#             print(f"Ollama Error: {e}")
#             # Fallback logic (Agar AI band ho toh basic search result dikha do)
#             if matched_products.exists():
#                 top_product = matched_products.first()
#                 ai_reply = f"AI offline hai, par mujhe **{top_product.name}** mila hai ₹{top_product.sale_price} ka. Kya add karu?"
#             else:
#                 ai_reply = "Maaf kijiye, abhi main connect nahi kar paa raha hu."

#         return Response({"reply": ai_reply})