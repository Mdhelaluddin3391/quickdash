from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from django.conf import settings
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from .utils import create_tokens_with_session
from .models import EmployeeProfile  # <-- Role check karne ke liye import kiya

User = get_user_model()

class GoogleLoginView(APIView):
    """
    Google Login ONLY for Admin Panel.
    Restricts Customers, Riders, and regular Employees (Pickers/Packers).
    """
    permission_classes = []

    def post(self, request):
        token = request.data.get('token')
        if not token:
            return Response({'error': 'Token required'}, status=400)

        try:
            # 1. Verify Google Token
            id_info = id_token.verify_oauth2_token(
                token, 
                google_requests.Request(), 
                settings.GOOGLE_CLIENT_ID
            )

            email = id_info.get('email')
            
            # 2. Domain Check (Sirf tumhari company ka email)
            if not email.endswith('@quickdash.com'):
                return Response({'error': 'Unauthorized domain.'}, status=403)

            # 3. Find User
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return Response({'error': 'User not found. Contact HR.'}, status=404)

            # ============================================================
            # 4. STRICT PERMISSION CHECK (Admin Panel Only)
            # ============================================================
            
            # Allowed Roles list define karein
            admin_panel_roles = [
                EmployeeProfile.Role.MANAGER,
                EmployeeProfile.Role.SUPERVISOR,
                EmployeeProfile.Role.ADMIN,
                EmployeeProfile.Role.AUDITOR
            ]

            is_authorized = False

            # Check A: Agar user Superuser ya Django Staff hai -> Allowed
            if user.is_superuser or user.is_staff:
                is_authorized = True
            
            # Check B: Agar user Employee hai, toh uska Role check karein
            elif user.is_employee and hasattr(user, 'employee_profile'):
                if user.employee_profile.role in admin_panel_roles:
                    is_authorized = True
            
            # Agar permission nahi mili (Customer, Rider, ya Picker/Packer hai)
            if not is_authorized:
                return Response(
                    {'error': 'Access Denied: This portal is for Admins & Managers only.'}, 
                    status=403
                )

            # 5. Generate Tokens (Role = ADMIN_PANEL set karke)
            tokens = create_tokens_with_session(
                user=user,
                role="ADMIN_PANEL",
                client=request.META.get('HTTP_USER_AGENT', 'GoogleLogin'),
                request=request
            )

            return Response({
                **tokens,
                "user": {
                    "full_name": user.full_name,
                    "email": user.email,
                    "role": "Admin/Manager"
                }
            })

        except ValueError:
            return Response({'error': 'Invalid Google Token'}, status=400)