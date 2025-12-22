# # config/urls.py

# from django.contrib import admin
# from django.urls import path, include
# from django.views.generic import TemplateView
# from django.conf import settings
# from django.conf.urls.static import static

# # FIX: Security Hardening
# # Ensure ADMIN_URL does not start with a slash for path() and has a trailing slash
# # Example: If settings.ADMIN_URL is "secret-admin", this becomes "secret-admin/"
# admin_url = settings.ADMIN_URL.strip("/") + "/"

# urlpatterns = [
#     # --- Admin Panels (HARDENED) ---
#     path(admin_url, admin.site.urls),
#     path("admin-panel/", include("apps.web_admin.urls")),

#     # --- APIs ---
#     path("api/v1/auth/", include("apps.accounts.urls")),
#     path("api/v1/wms/", include("apps.warehouse.urls")),
#     path("api/v1/orders/", include("apps.orders.urls")),
#     path("api/v1/delivery/", include("apps.delivery.urls")),
#     path("api/v1/payments/", include("apps.payments.urls")),
#     path("api/v1/catalog/", include("apps.catalog.urls")),
#     path("api/v1/inventory/", include("apps.inventory.urls")),
#     path("api/v1/analytics/", include("apps.analytics.urls")),
#     path("api/v1/notifications/", include("apps.notifications.urls")),
#     path("api/v1/utils/", include("apps.utils.urls")),

#     # --- Frontend Pages ---
#     path("", TemplateView.as_view(template_name="frontend/index.html"), name="home"),
#     path("index.html", TemplateView.as_view(template_name="frontend/index.html")),
#     path("auth.html", TemplateView.as_view(template_name="frontend/auth/login.html"), name="auth"),
    
#     # Catalog
#     path("category.html", TemplateView.as_view(template_name="frontend/catalog/category_list.html"), name="category"),
#     path("category_detail.html", TemplateView.as_view(template_name="frontend/catalog/product_list.html"), name="category-detail"),
#     path("search_results.html", TemplateView.as_view(template_name="frontend/catalog/product_list.html"), name="search"),
#     path("product.html", TemplateView.as_view(template_name="frontend/catalog/product_detail.html"), name="product"),

#     # Checkout
#     path("cart.html", TemplateView.as_view(template_name="frontend/checkout/cart.html"), name="cart"),
#     path("checkout.html", TemplateView.as_view(template_name="frontend/checkout/checkout.html"), name="checkout"),
#     path("order_success.html", TemplateView.as_view(template_name="frontend/checkout/success.html"), name="order-success"),

#     # User Account
#     path("profile.html", TemplateView.as_view(template_name="frontend/account/dashboard.html"), name="profile"),
#     path("orders.html", TemplateView.as_view(template_name="frontend/account/orders.html"), name="orders"),
#     path("order_detail.html", TemplateView.as_view(template_name="frontend/account/order_detail.html"), name="order-detail"),
#     path("addresses.html", TemplateView.as_view(template_name="frontend/account/addresses.html"), name="addresses"),
#     path("track_order.html", TemplateView.as_view(template_name="frontend/account/track_order.html"), name="track-order"),

#     # Support
#     path("support.html", TemplateView.as_view(template_name="frontend/support/help_center.html"), name="support"),
#     path("support_chat.html", TemplateView.as_view(template_name="frontend/support/chat.html"), name="support-chat"),
    
#     # Errors
#     path("location_denied.html", TemplateView.as_view(template_name="frontend/pages/location_permission.html"), name="location-denied"),
#     path("404.html", TemplateView.as_view(template_name="frontend/pages/404.html"), name="not-found"),
#     path("service-unavailable.html", TemplateView.as_view(template_name="frontend/pages/not_serviceable.html"), name="not-serviceable"),
# ]

# # Serve media files in development
# if settings.DEBUG:
#     urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
#     urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)




from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Core Apps
    path('api/v1/accounts/', include('apps.accounts.urls')),
    path('api/v1/customers/', include('apps.customers.urls')), # New V2 App
    path('api/v1/riders/', include('apps.riders.urls')),       # New V2 App
    path('api/v1/catalog/', include('apps.catalog.urls')),
    path('api/v1/inventory/', include('apps.inventory.urls')),
    path('api/v1/orders/', include('apps.orders.urls')),
    path('api/v1/delivery/', include('apps.delivery.urls')),
    path('api/v1/payments/', include('apps.payments.urls')),
    path('api/v1/notifications/', include('apps.notifications.urls')),
    path('api/v1/customers/', include('apps.customers.urls')),
    
    # Observability (Prometheus)
    path('prometheus/', include('django_prometheus.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)