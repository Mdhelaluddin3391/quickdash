# apps/web_admin/views.py
from django.shortcuts import render
from django.views import View
from django.conf import settings

class AdminLoginView(View):
    def get(self, request):
        context = {
            "google_client_id": settings.GOOGLE_CLIENT_ID
        }
        return render(request, 'web_admin/login.html', context)

class AdminDashboardView(View):
    def get(self, request):
        context = {
            "api_base": "/api/v1", 
        }
        return render(request, 'web_admin/dashboard.html', context)