from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from django.conf import settings
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from .utils import create_tokens_with_session
from .models import EmployeeProfile

User = get_user_model()

class GoogleLoginView(APIView):
    """
    Google Login for Admin Panel.
    Updated: Allows Gmail for testing/development.
    """
    permission_classes = []

    def post(self, request):
        token = request.data.get('token')
        if not token:
            return Response({'error': 'Token required'}, status=400)

        try:
            # 1. Verify Google Token
            # Note: Production mein CLIENT_ID zaroor set karna settings.py mein
            id_info = id_token.verify_oauth2_token(
                token, 
                google_requests.Request(), 
                settings.GOOGLE_CLIENT_ID
            )

            email = id_info.get('email')
            
            # --- FIX: Domain Check Removed for Development ---
            # Agar production ho toh ise uncomment kar dena
            # if not email.endswith('@quickdash.com'):
            #     return Response({'error': 'Unauthorized domain.'}, status=403)

            # 2. Find User
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                # Optional: Agar user nahi hai toh create mat karo admin ke liye
                # Ya fir error do
                return Response({'error': f'User with email {email} not found. Please register first or contact HR.'}, status=404)

            # ============================================================
            # 3. PERMISSION CHECK (Admin Panel Only)
            # ============================================================
            
            admin_panel_roles = [
                EmployeeProfile.Role.MANAGER,
                EmployeeProfile.Role.SUPERVISOR,
                EmployeeProfile.Role.ADMIN,
                EmployeeProfile.Role.AUDITOR
            ]

            is_authorized = False

            # Check A: Superuser ya Django Staff
            if user.is_superuser or user.is_staff:
                is_authorized = True
            
            # Check B: Employee Role
            elif user.is_employee and hasattr(user, 'employee_profile'):
                if user.employee_profile.role in admin_panel_roles:
                    is_authorized = True
            
            if not is_authorized:
                return Response(
                    {'error': 'Access Denied: This portal is for Admins & Managers only.'}, 
                    status=403
                )

            # 4. Generate Tokens
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

        except ValueError as e:
            return Response({'error': f'Invalid Google Token: {str(e)}'}, status=400)
        except Exception as e:
            return Response({'error': f'Login Failed: {str(e)}'}, status=500)