from django.db import transaction
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import User, CustomerProfile, PhoneOTP
from .serializers import RequestOTPSerializer, VerifyOTPSerializer
from .utils import create_and_send_otp, normalize_phone, create_tokens_with_session
# apps/accounts/views.py top par add karein
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken


# ========== Base OTP Views ==========

class BaseRequestOTPView(APIView):
    login_type = None  # "CUSTOMER" / "RIDER" / "EMPLOYEE"

    def post(self, request, *args, **kwargs):
        serializer = RequestOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]

        try:
            # Rate limiting ko waapas add kiya gaya hai
            check_otp_rate_limit(
                phone=phone,
                login_type=self.login_type,
                ip=get_client_ip(request),
            )
            # Request ko handle karna
            return self.handle_request(phone)
        
        except ValidationError as e:
            # Rate limit error ko handle karna
            return Response(
                {"detail": str(e)}, status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        except ValueError as e:
            # Baaki errors (jaise user not found)
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def handle_request(self, phone: str):
        raise NotImplementedError


class BaseVerifyOTPView(APIView):
    login_type = None
    role_claim = None
    client_claim = None

    def post(self, request, *args, **kwargs):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]
        otp = serializer.validated_data["otp"]

        try:
            return self.handle_verify(request, phone, otp)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @transaction.atomic
    def _validate_otp(self, phone: str, otp_code: str) -> PhoneOTP:
        """
        Atomically OTP ko check aur 'used' mark karta hai.
        """
        otp_obj = (
            PhoneOTP.objects.select_for_update()
            .filter(phone=phone, login_type=self.login_type)
            .order_by("-created_at")
            .first()
        )
        if not otp_obj:
            raise ValueError("OTP not found. Please request again.")

        ok, reason = otp_obj.is_valid(otp_code)
        if not ok:
            raise ValueError(reason)

        otp_obj.is_used = True
        otp_obj.save(update_fields=["is_used"])
        return otp_obj

    def handle_verify(self, request, phone: str, otp_code: str):
        raise NotImplementedError


# ========== CUSTOMER AUTH ==========

class CustomerRequestOTPView(APIView):
    def post(self, request):
        serializer = RequestOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        create_and_send_otp(serializer.validated_data["phone"], "CUSTOMER")
        return Response({"detail": "OTP sent."})



class CustomerVerifyOTPView(APIView):
    @transaction.atomic
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone, otp_code = serializer.validated_data["phone"], serializer.validated_data["otp"]

        otp_obj = PhoneOTP.objects.filter(phone=phone, login_type="CUSTOMER").order_by("-created_at").first()
        if not otp_obj: return Response({"detail": "OTP not found"}, status=400)
        
        valid, msg = otp_obj.is_valid(otp_code)
        if not valid: return Response({"detail": msg}, status=400)
        otp_obj.is_used = True
        otp_obj.save()

        user, _ = User.objects.get_or_create(phone=phone, defaults={"app_role": "CUSTOMER"})
        if not user.is_customer:
            user.is_customer = True
            user.save()
        CustomerProfile.objects.get_or_create(user=user)

        tokens = create_tokens_with_session(user=user, role="CUSTOMER", client="customer_app", request=request)
        return Response(tokens)

# ========== RIDER AUTH ==========

class RiderRequestOTPView(BaseRequestOTPView):
    login_type = "RIDER"

    def handle_request(self, phone: str):
        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            raise ValueError("This phone is not registered as rider.")

        if not user.is_rider or not hasattr(user, "rider_profile"):
            raise ValueError("Rider profile not found for this phone.")

        if user.rider_profile.status != "ACTIVE":
            raise ValueError("Rider is not active/approved.")

        create_and_send_otp(phone, self.login_type)
        return Response({"detail": "OTP sent to rider phone."})


class RiderVerifyOTPView(BaseVerifyOTPView):
    login_type = "RIDER"
    role_claim = "RIDER"
    client_claim = "rider_app"

    @transaction.atomic
    def handle_verify(self, request, phone: str, otp_code: str):
        phone = normalize_phone(phone)
        
        # Step 1: OTP Validate karein
        self._validate_otp(phone, otp_code)

        # Step 2: User verify karein
        try:
            user = User.objects.get(phone=phone, is_rider=True)
        except User.DoesNotExist:
            raise ValueError("Rider profile not found.")

        rider = getattr(user, "rider_profile", None)
        if not rider:
            raise ValueError("Rider profile not found.")
        if rider.status != "ACTIVE":
            raise ValueError("Rider is not active.")

        device_info = {
            "device_id": request.data.get("device_id", ""),
            "device_model": request.data.get("device_model", ""),
            "os_version": request.data.get("os_version", ""),
        }

        tokens = create_tokens_with_session(
            user=user,
            role=self.role_claim,
            client=self.client_claim,
            extra_claims={
                "rider_id": str(rider.id), # UUIDs
                "rider_code": rider.rider_code,
            },
            device_info=device_info,
            request=request,
            single_session_for_client=True, # SINGLE DEVICE POLICY
        )
        return Response(tokens, status=status.HTTP_200_OK)


# ========== EMPLOYEE AUTH ==========

class EmployeeRequestOTPView(BaseRequestOTPView):
    login_type = "EMPLOYEE"

    def handle_request(self, phone: str):
        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            raise ValueError("This phone is not registered as employee.")

        if not user.is_employee or not hasattr(user, "employee_profile"):
            raise ValueError("Employee profile not found for this phone.")

        if not user.employee_profile.is_active_employee:
            raise ValueError("Employee is not active.")

        create_and_send_otp(phone, self.login_type)
        return Response({"detail": "OTP sent to employee phone."})


class EmployeeVerifyOTPView(BaseVerifyOTPView):
    login_type = "EMPLOYEE"
    role_claim = "EMPLOYEE"
    client_claim = "employee_app"

    @transaction.atomic
    def handle_verify(self, request, phone: str, otp_code: str):
        phone = normalize_phone(phone)
        
        # Step 1: OTP Validate karein
        self._validate_otp(phone, otp_code)

        # Step 2: User verify karein
        try:
            user = User.objects.get(phone=phone, is_employee=True)
        except User.DoesNotExist:
            raise ValueError("Employee profile not found.")

        emp = getattr(user, "employee_profile", None)
        if not emp:
            raise ValueError("Employee profile not found.")
        if not emp.is_active_employee:
            raise ValueError("Employee is not active.")

        device_info = {
            "device_id": request.data.get("device_id", ""),
            "device_model": request.data.get("device_model", ""),
            "os_version": request.data.get("os_version", ""),
        }

        tokens = create_tokens_with_session(
            user=user,
            role=self.role_claim,
            client=self.client_claim,
            extra_claims={
                "employee_id": str(emp.id), # UUIDs
                "employee_code": emp.employee_code,
                "warehouse_code": emp.warehouse_code,
                "employee_role": emp.role,
            },
            device_info=device_info,
            request=request,
            single_session_for_client=True, # SINGLE DEVICE POLICY
        )
        return Response(tokens, status=status.HTTP_200_OK)

# ========== LOGOUT / SESSION REVOKE ==========

class LogoutView(APIView):
    """
    Enterprise-style logout:
    - refresh token blacklist
    - UserSession mark inactive
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"detail": "Refresh token required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)
            jti = str(token["jti"])
            # blacklist (if blacklist app enabled)
            token.blacklist()
        except TokenError:
            return Response(
                {"detail": "Invalid or expired refresh token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        UserSession.objects.filter(jti=jti, is_active=True).update(
            is_active=False, revoked_at=timezone.now()
        )

        return Response({"detail": "Logged out successfully."}, status=status.HTTP_200_OK)


# ========== "ME" ENDPOINTS (FOR TESTING & CLIENTS) ==========

class CustomerMeView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def get(self, request):
        user = request.user
        profile = getattr(user, "customer_profile", None)
        return Response(
            {
                "phone": user.phone,
                "full_name": user.full_name,
                "customer_id": profile.id if profile else None,
                "default_address": getattr(profile, "default_address", ""),
            }
        )


class RiderMeView(APIView):
    permission_classes = [IsAuthenticated, IsRider]

    def get(self, request):
        user = request.user
        rider = getattr(user, "rider_profile", None)
        return Response(
            {
                "phone": user.phone,
                "full_name": user.full_name,
                "rider_id": rider.id if rider else None,
                "rider_code": getattr(rider, "rider_code", None),
                "status": getattr(rider, "status", None),
            }
        )


class EmployeeMeView(APIView):
    permission_classes = [IsAuthenticated, IsEmployee]

    def get(self, request):
        user = request.user
        emp = getattr(user, "employee_profile", None)
        return Response(
            {
                "phone": user.phone,
                "full_name": user.full_name,
                "employee_id": emp.id if emp else None,
                "employee_code": getattr(emp, "employee_code", None),
                "role": getattr(emp, "role", None),
                "warehouse_code": getattr(emp, "warehouse_code", None),
            }
        )


# ========== ADMIN LOGIN (email/phone + password) ==========

class AdminLoginView(APIView):
    """
    Admin / internal tools ke liye:
    - identifier = email ya phone
    - password
    - user.is_staff True hona chahiye
    """

    def post(self, request, *args, **kwargs):
        identifier = request.data.get("identifier")
        password = request.data.get("password")

        if not identifier or not password:
            return Response(
                {"detail": "identifier and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Try email first, then phone
        user = (
            User.objects.filter(email__iexact=identifier).first()
            or User.objects.filter(phone=identifier).first()
        )

        if not user or not user.is_staff:
            return Response(
                {"detail": "Admin not found or not allowed."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.check_password(password):
            return Response(
                {"detail": "Invalid credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        device_info = {
            "device_id": request.data.get("device_id", ""),
            "device_model": request.data.get("device_model", ""),
            "os_version": request.data.get("os_version", ""),
        }


        tokens = create_tokens_with_session(
            user=user,
            role="ADMIN",
            client="admin_panel",
            extra_claims={"admin_id": user.id},
            request=request,
            device_info=device_info,
            # request=request,
        )
        return Response(tokens, status=status.HTTP_200_OK)


class AdminMeView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        user = request.user
        return Response(
            {
                "id": user.id,
                "phone": user.phone,
                "email": user.email,
                "full_name": user.full_name,
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
            }
        )


# ========== ADMIN RIDER / EMPLOYEE MANAGEMENT ==========

class AdminCreateRiderView(APIView):
    """
    Staff-only API:
    - Rider create + ACTIVE status
    """

    permission_classes = [IsAuthenticated, IsAdmin]

    @transaction.atomic
    def post(self, request):
        serializer = AdminCreateRiderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]
        full_name = serializer.validated_data["full_name"]
        vehicle_type = serializer.validated_data.get("vehicle_type", "")

        # FIX: Default mein app_role="RIDER" set kiya
        user, created = User.objects.get_or_create(
            phone=phone, defaults={"full_name": full_name, "app_role": "RIDER"}
        )
        
        update_fields = []
        if not created and user.full_name != full_name:
            user.full_name = full_name
            update_fields.append("full_name")
            
        if not user.is_rider:
            user.is_rider = True
            update_fields.append("is_rider")
        
        # FIX: Agar user pehle se tha (jaise customer) toh uska app_role "RIDER" set karein
        if user.app_role != "RIDER":
            user.app_role = "RIDER"
            update_fields.append("app_role")
            
        if update_fields:
            user.save(update_fields=update_fields)

        # simple rider_code generator
        if hasattr(user, "rider_profile"):
            rider = user.rider_profile
            rider.vehicle_type = vehicle_type
            rider.status = "ACTIVE"
            rider.save(update_fields=["vehicle_type", "status"])
        else:
            last = RiderProfile.objects.order_by("-id").first()
            next_id = (last.id + 1) if last else 1
            rider_code = f"RD-{next_id:05d}"
            rider = RiderProfile.objects.create(
                user=user,
                rider_code=rider_code,
                status="ACTIVE",
                vehicle_type=vehicle_type,
            )

        return Response(
            {
                "id": rider.id,
                "rider_code": rider.rider_code,
                "phone": user.phone,
                "full_name": user.full_name,
                "status": rider.status,
            },
            status=status.HTTP_201_CREATED,
        )


class AdminChangeRiderStatusView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request):
        serializer = AdminChangeRiderStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rider_id = serializer.validated_data["id"]
        status_value = serializer.validated_data["status"]

        valid_statuses = dict(RiderProfile.STATUS_CHOICES).keys()
        if status_value not in valid_statuses:
            return Response(
                {"detail": "Invalid status."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            rider = RiderProfile.objects.get(id=rider_id)
        except RiderProfile.DoesNotExist:
            return Response(
                {"detail": "Rider not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        rider.status = status_value
        rider.save(update_fields=["status"])
        
        # FEATURE: Agar rider "SUSPENDED" hai to use fauran logout kar dein
        if status_value == "SUSPENDED":
            UserSession.objects.filter(user=rider.user, client="rider_app", is_active=True).update(
                is_active=False, revoked_at=timezone.now()
            )

        return Response({"detail": "Rider status updated."})

class AdminCreateEmployeeView(APIView):
    """
    Staff-only API:
    - Employee create with role + warehouse
    """

    permission_classes = [IsAuthenticated, IsAdmin]

    @transaction.atomic
    def post(self, request):
        serializer = AdminCreateEmployeeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]
        full_name = serializer.validated_data["full_name"]
        employee_code = serializer.validated_data["employee_code"]
        role = serializer.validated_data["role"]
        warehouse_code = serializer.validated_data["warehouse_code"]

        # FIX: Default mein app_role="EMPLOYEE" set kiya
        user, created = User.objects.get_or_create(
            phone=phone, defaults={"full_name": full_name, "app_role": "EMPLOYEE"}
        )
        
        update_fields = []
        if not created and user.full_name != full_name:
            user.full_name = full_name
            update_fields.append("full_name")
            
        if not user.is_employee:
            user.is_employee = True
            update_fields.append("is_employee")
            
        # FIX: Agar user pehle se tha (jaise customer) toh uska app_role "EMPLOYEE" set karein
        if user.app_role != "EMPLOYEE":
            user.app_role = "EMPLOYEE"
            update_fields.append("app_role")

        if update_fields:
            user.save(update_fields=update_fields)

        if hasattr(user, "employee_profile"):
            emp = user.employee_profile
            emp.employee_code = employee_code
            emp.role = role
            emp.warehouse_code = warehouse_code
            emp.is_active_employee = True
            emp.save(
                update_fields=[
                    "employee_code",
                    "role",
                    "warehouse_code",
                    "is_active_employee",
                ]
            )
        else:
            emp = EmployeeProfile.objects.create(
                user=user,
                employee_code=employee_code,
                role=role,
                warehouse_code=warehouse_code,
                is_active_employee=True,
            )

        return Response(
            {
                "id": emp.id,
                "employee_code": emp.employee_code,
                "phone": user.phone,
                "full_name": user.full_name,
                "role": emp.role,
                "warehouse_code": emp.warehouse_code,
            },
            status=status.HTTP_201_CREATED,
        )


class AdminChangeEmployeeStatusView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request):
        serializer = AdminChangeEmployeeStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        emp_id = serializer.validated_data["id"]
        status_value = serializer.validated_data["status"]

        if status_value not in ["ACTIVE", "INACTIVE"]:
            return Response(
                {"detail": "Status must be ACTIVE or INACTIVE."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            emp = EmployeeProfile.objects.get(id=emp_id)
        except EmployeeProfile.DoesNotExist:
            return Response(
                {"detail": "Employee not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        emp.is_active_employee = status_value == "ACTIVE"
        emp.save(update_fields=["is_active_employee"])
        
        # FEATURE: Agar employee "INACTIVE" hai to use fauran logout kar dein
        if status_value == "INACTIVE":
            UserSession.objects.filter(user=emp.user, client="employee_app", is_active=True).update(
                is_active=False, revoked_at=timezone.now()
            )

        return Response({"detail": "Employee status updated."})


# ========== CUSTOM TOKEN REFRESH VIEW ==========

class CustomTokenRefreshView(TokenRefreshView):
    """
    Standard TokenRefreshView ko override kiya gaya hai taaki hum:
    1. Token Rotation laagu kar sakein (naya refresh token return karein).
    2. Hamare UserSession model mein naye token ka 'jti' update kar sakein.
    """
    def post(self, request, *args, **kwargs):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            raise InvalidToken("Refresh token not provided")

        try:
            # Hamara custom utility function (utils.py se)
            # Yeh rotation aur session update, dono handle karta hai
            rotated_tokens = rotate_refresh_token(
                old_refresh_token_str=refresh_token,
                request=request
            )
            return Response(rotated_tokens, status=status.HTTP_200_OK)

        except TokenError as e:
            # Agar token invalid, expired ya revoke ho chuka hai
            raise InvalidToken(e.args[0])
        except Exception as e:
            # Koi aur galti (jaise session nahi mila)
            return Response(
                {"detail": f"Token rotation failed: {str(e)}"}, 
                status=status.HTTP_400_BAD_REQUEST
            )


# ========== ADMIN PASSWORD RESET ==========

class AdminForgotPasswordView(APIView):
    """
    Admin ke liye password reset request.
    Ye 'identifier' (email ya phone) lega.
    """
    def post(self, request, *args, **kwargs):
        serializer = AdminForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        identifier = serializer.validated_data["identifier"]

        # User ko email ya phone se dhoondein
        user = User.objects.filter(
            Q(email__iexact=identifier) | Q(phone=identifier),
            is_staff=True,
            is_active=True
        ).first()

        if not user:
            # User ko nahi batana ki email/phone exist karta hai ya nahi (security)
            return Response(
                {"detail": "If an account matches, a reset link will be sent."},
                status=status.HTTP_200_OK
            )
        
        if not user.email:
            # Agar user ka email hi nahi hai to reset nahi kar sakte
            return Response(
                {"detail": "This admin account does not have an email associated."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Token create karein
        reset_token = PasswordResetToken.create_token(user=user)
        
        # Email task ko trigger karein
        send_admin_password_reset_email_task.delay(
            user_email=user.email,
            user_name=user.full_name or user.phone,
            reset_token=str(reset_token.token)
        )

        return Response(
            {"detail": "If an account matches, a reset link will be sent."},
            status=status.HTTP_200_OK
        )


class AdminResetPasswordView(APIView):
    """
    Token aur naye password ka istemal karke password reset karein.
    """
    def post(self, request, *args, **kwargs):
        serializer = AdminResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        token_value = serializer.validated_data["token"]
        new_password = serializer.validated_data["new_password"]

        # Token ko database mein dhoondein
        try:
            token_obj = PasswordResetToken.objects.get(token=token_value)
        except PasswordResetToken.DoesNotExist:
            return Response(
                {"detail": "Invalid or expired token."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        if not token_obj.is_valid():
            return Response(
                {"detail": "Invalid or expired token."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Password set karein aur token ko 'used' mark karein
        user = token_obj.user
        user.set_password(new_password)
        user.save()
        
        token_obj.is_used = True
        token_obj.save()
        
        # Bonus: Password reset ke baad purane saare sessions revoke kar dein
        UserSession.objects.filter(user=user, is_active=True).update(
            is_active=False,
            revoked_at=timezone.now()
        )

        return Response(
            {"detail": "Password has been reset successfully."},
            status=status.HTTP_200_OK
        )