"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

"""
URL configuration for config project.
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView  # [IMPORTANT] Ye import zaroori hai

urlpatterns = [
    # --- Admin Panels ---
    path("admin/", admin.site.urls),
    path("admin-panel/", include("apps.web_admin.urls")),

    # --- APIs (Backend Logic) ---
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/wms/", include("apps.warehouse.urls")),
    path("api/v1/orders/", include("apps.orders.urls")),
    path("api/v1/delivery/", include("apps.delivery.urls")),
    path("api/v1/payments/", include("apps.payments.urls")),
    path("api/v1/catalog/", include("apps.catalog.urls")),
    path("api/v1/inventory/", include("apps.inventory.urls")),
    path("api/v1/analytics/", include("apps.analytics.urls")),
    path("api/v1/notifications/", include("apps.notifications.urls")),
    path("api/v1/utils/", include("apps.utils.urls")),

    # --- Frontend Pages (Customer App) ---
    # Ye mapping zaroori hai taaki 'index.html' URL par index page khule
    path("", TemplateView.as_view(template_name="frontend/index.html"), name="home"),
    path("index.html", TemplateView.as_view(template_name="frontend/index.html")),
    
    path("auth.html", TemplateView.as_view(template_name="frontend/auth.html"), name="auth"),
    path("cart.html", TemplateView.as_view(template_name="frontend/cart.html"), name="cart"),
    path("checkout.html", TemplateView.as_view(template_name="frontend/checkout.html"), name="checkout"),
    path("product.html", TemplateView.as_view(template_name="frontend/product.html"), name="product"),
    path("category.html", TemplateView.as_view(template_name="frontend/category.html"), name="category"),
    path("category_detail.html", TemplateView.as_view(template_name="frontend/category_detail.html"), name="category-detail"),
    path("profile.html", TemplateView.as_view(template_name="frontend/profile.html"), name="profile"),
    path("search_results.html", TemplateView.as_view(template_name="frontend/search_results.html"), name="search"),
    path("order_detail.html", TemplateView.as_view(template_name="frontend/order_detail.html"), name="order-detail"),
    path("order_success.html", TemplateView.as_view(template_name="frontend/order_success.html"), name="order-success"),
    path("track_order.html", TemplateView.as_view(template_name="frontend/track_order.html"), name="track-order"),
    path("location_denied.html", TemplateView.as_view(template_name="frontend/location_denied.html"), name="location-denied"),
    path("support.html", TemplateView.as_view(template_name="frontend/support.html"), name="support"),
    path("support_chat.html", TemplateView.as_view(template_name="frontend/support_chat.html"), name="support-chat"),
]

