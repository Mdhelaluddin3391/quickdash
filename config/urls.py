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
from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse  # <--- THIS LINE WAS MISSING


def home_view(request):
    return HttpResponse("QuickDash Server is Running! ")


urlpatterns = [
    path("", home_view),

    path("admin/", admin.site.urls),

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

]

