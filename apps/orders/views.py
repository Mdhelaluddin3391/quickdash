from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from .models.cart import Cart, CartItem
from .models.order import Order
from .serializers import CartSerializer, OrderSerializer
from .services import OrderService
from apps.catalog.models import Product

class CartViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        serializer = CartSerializer(cart)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def add_item(self, request):
        product_id = request.data.get('product_id')
        qty = int(request.data.get('quantity', 1))
        
        cart, _ = Cart.objects.get_or_create(user=request.user)
        product = Product.objects.get(id=product_id)
        
        item, created = CartItem.objects.get_or_create(cart=cart, product=product)
        if not created:
            item.quantity += qty
        else:
            item.quantity = qty
        item.save()
        
        return Response(CartSerializer(cart).data)

    @action(detail=False, methods=['post'])
    def clear(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        cart.items.all().delete()
        return Response({"status": "cleared"})

class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related('items')

    def create(self, request):
        """
        Checkout Endpoint.
        Expects: { "address_id": 1, "lat": 12.97, "lng": 77.59 }
        """
        address_id = request.data.get('address_id')
        lat = request.data.get('lat')
        lng = request.data.get('lng')
        
        try:
            order = OrderService.create_order_from_cart(
                user=request.user,
                address_id=address_id,
                lat=lat,
                lng=lng
            )
            return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)