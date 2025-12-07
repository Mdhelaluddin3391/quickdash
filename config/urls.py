from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

urlpatterns = [
    # --- Admin Panels ---
    path("admin/", admin.site.urls),
    path("admin-panel/", include("apps.web_admin.urls")),

    # --- APIs ---
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

    # --- Frontend Pages (Mapped to NEW Structure) ---

    # 1. Home
    path("", TemplateView.as_view(template_name="frontend/index.html"), name="home"),
    path("index.html", TemplateView.as_view(template_name="frontend/index.html")),

    # 2. Auth
    path("auth.html", TemplateView.as_view(template_name="frontend/auth/login.html"), name="auth"),

    # 3. Catalog & Products
    path("category.html", TemplateView.as_view(template_name="frontend/catalog/category_list.html"), name="category"),
    # Category Detail & Search both use Product List
    path("category_detail.html", TemplateView.as_view(template_name="frontend/catalog/product_list.html"), name="category-detail"),
    path("search_results.html", TemplateView.as_view(template_name="frontend/catalog/product_list.html"), name="search"),
    path("product.html", TemplateView.as_view(template_name="frontend/catalog/product_detail.html"), name="product"),

    # 4. Checkout Flow
    path("cart.html", TemplateView.as_view(template_name="frontend/checkout/cart.html"), name="cart"),
    path("checkout.html", TemplateView.as_view(template_name="frontend/checkout/checkout.html"), name="checkout"),
    path("order_success.html", TemplateView.as_view(template_name="frontend/checkout/success.html"), name="order-success"),

    # 5. User Account
    # Profile URL maps to Dashboard template
    path("profile.html", TemplateView.as_view(template_name="frontend/account/dashboard.html"), name="profile"),
    path("orders.html", TemplateView.as_view(template_name="frontend/account/orders.html"), name="orders"),
    path("order_detail.html", TemplateView.as_view(template_name="frontend/account/order_detail.html"), name="order-detail"),
    path("addresses.html", TemplateView.as_view(template_name="frontend/account/addresses.html"), name="addresses"),
    path("track_order.html", TemplateView.as_view(template_name="frontend/account/track_order.html"), name="track-order"),

    # 6. Support & Utility
    path("support.html", TemplateView.as_view(template_name="frontend/support/help_center.html"), name="support"),
    path("support_chat.html", TemplateView.as_view(template_name="frontend/support/chat.html"), name="support-chat"),
    
    # Errors & Permissions
    path("location_denied.html", TemplateView.as_view(template_name="frontend/pages/location_permission.html"), name="location-denied"),
    path("404.html", TemplateView.as_view(template_name="frontend/pages/404.html"), name="not-found"),
    path("service-unavailable.html", TemplateView.as_view(template_name="frontend/pages/not_serviceable.html"), name="not-serviceable"),
]