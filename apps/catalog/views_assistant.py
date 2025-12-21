# apps/catalog/views_assistant.py

import os
import logging
import requests
import json
from decimal import Decimal
from django.db.models import Q, Sum
from django.conf import settings
from django.contrib.postgres.search import TrigramSimilarity
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

# Groq library (Make sure pip install groq is done)
try:
    from groq import Groq
except ImportError:
    Groq = None  # Handle case where library is missing locally

from apps.catalog.models import SKU
from apps.orders.models import Cart, CartItem

logger = logging.getLogger(__name__)

class ShoppingAssistantView(APIView):
    """
    SMART HYBRID ASSISTANT
    ----------------------
    1. Local (Dev): Uses Ollama (Offline, Free) via 'host.docker.internal'
    2. Production (AWS): Uses Groq API (Fast, Cloud)
    
    Automatic switching based on 'AI_MODE' env variable.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        message = request.data.get("message", "").strip()
        user = request.user if request.user.is_authenticated else None
        
        # ---------------------------------------------------------
        # 1. CONTEXT BUILDERS (Cart & Inventory)
        # ---------------------------------------------------------
        
        # Cart Context
        cart_context = "Cart is empty."
        if user:
            cart, _ = Cart.objects.get_or_create(customer=user)
            total = cart.items.aggregate(t=Sum("total_price"))["t"] or 0
            if cart.items.exists():
                items = [f"{i.quantity} x {i.sku.name}" for i in cart.items.all()]
                cart_context = f"Cart Items: {', '.join(items)}. Total Bill: ₹{int(total)}"

        # Product Context (Database Search)
        product_context = self._get_product_context(message)

        # ---------------------------------------------------------
        # 2. SYSTEM PROMPT
        # ---------------------------------------------------------
        system_prompt = f"""
        You are 'QuickDash AI', a helpful and friendly grocery shopkeeper assistant.
        
        INVENTORY (Available Stock):
        {product_context}

        USER'S CART:
        {cart_context}

        INSTRUCTIONS:
        - Provide helpful answers in Hinglish (Hindi + English mix).
        - ONLY recommend products listed in the INVENTORY above.
        - If the user wants to buy, ask them to type "Add [Product Name]".
        - Keep answers short (max 2-3 sentences).
        """

        # ---------------------------------------------------------
        # 3. HYBRID AI SWITCH (OLLAMA vs GROQ)
        # ---------------------------------------------------------
        
        # Default is LOCAL unless specified in .env
        ai_mode = os.environ.get("AI_MODE", "LOCAL").upper()
        ai_reply = ""

        try:
            if ai_mode == "GROQ":
                # === OPTION A: PRODUCTION (GROQ CLOUD) ===
                if not Groq:
                    ai_reply = "Server Error: Groq library not installed."
                else:
                    api_key = os.environ.get("GROQ_API_KEY")
                    if not api_key:
                        ai_reply = "Server Config Error: Missing GROQ_API_KEY."
                    else:
                        client = Groq(api_key=api_key)
                        chat_completion = client.chat.completions.create(
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": message},
                            ],
                            model="llama3-8b-8192", # Very fast model
                            temperature=0.6,
                        )
                        ai_reply = chat_completion.choices[0].message.content

            else:
                # === OPTION B: DEVELOPMENT (LOCAL OLLAMA) ===
                # Docker container se host tak pahunchne ke liye URL
                ollama_url = "http://host.docker.internal:11434/api/chat"
                
                response = requests.post(
                    ollama_url,
                    json={
                        "model": "llama3",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": message},
                        ],
                        "stream": False
                    },
                    timeout=120  # Timeout increased for local CPU
                )
                
                if response.status_code == 200:
                    ai_reply = response.json().get("message", {}).get("content", "")
                else:
                    logger.error(f"Ollama Error: {response.text}")
                    ai_reply = "Local AI system is busy. Please try again."

        except requests.exceptions.ConnectionError:
            ai_reply = "Local AI not connected. Ensure Ollama is running."
        except Exception as e:
            logger.error(f"AI Assistant Error: {str(e)}")
            ai_reply = "Kuch technical gadbad ho gayi. Thodi der baad try karein."

        return Response({"reply": ai_reply})

    def _get_product_context(self, query):
        """
        RAG Logic: Database se relevant products dhoondna
        """
        stopwords = {"add", "want", "show", "price", "bhai", "chahiye", "available", "hai", "kya"}
        clean_query = " ".join([w for w in query.lower().split() if w not in stopwords])
        
        if len(clean_query) < 2: 
            return "No specific product searched."

        # Search priority: Trigram similarity -> Contains
        products = SKU.objects.annotate(
            similarity=TrigramSimilarity('name', clean_query)
        ).filter(
            Q(similarity__gt=0.1) | Q(name__icontains=clean_query),
            is_active=True
        ).order_by('-similarity')[:5]

        if not products.exists():
            return "No matching products found in inventory."

        context_list = []
        for p in products:
            context_list.append(f"- {p.name}: ₹{p.sale_price}/{p.unit}")
        
        return "\n".join(context_list)