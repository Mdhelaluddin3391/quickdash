from django.shortcuts import render
from django.views import View
from django.conf import settings

class AdminLoginView(View):
    def get(self, request):
        return render(request, 'web_admin/login.html')

class AdminDashboardView(View):
    def get(self, request):
        # We pass the API_BASE_URL to the template so JS can use it
        context = {
            "api_base": "/api/v1", 
        }
        return render(request, 'web_admin/dashboard.html', context)