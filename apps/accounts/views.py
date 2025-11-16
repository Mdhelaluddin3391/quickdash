from django.db import transaction
from django.utils import timezone

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from django.core.exceptions import ValidationError
from .models import (
    User,
    CustomerProfile,
    RiderProfile,
    EmployeeProfile,
    PhoneOTP,
    UserSession,
)
from .serializers import (
    RequestOTPSerializer,
    VerifyOTPSerializer,
    AdminCreateRiderSerializer,
    AdminCreateEmployeeSerializer,
    AdminChangeRiderStatusSerializer,
    AdminChangeEmployeeStatusSerializer,
)
from .utils import create_and_send_otp, normalize_phone, create_tokens_with_session,check_otp_rate_limit,get_client_ip
from .permissions import IsCustomer, IsRider, IsEmployee, IsAdmin


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

    def handle_verify(self, request, phone: str, otp_code: str):
        raise NotImplementedError

    def _get_latest_otp(self, phone: str):
        return (
            PhoneOTP.objects.filter(phone=phone, login_type=self.login_type)
            .order_by("-created_at")
            .first()
        )


# ========== CUSTOMER AUTH ==========

class CustomerRequestOTPView(BaseRequestOTPView):
    login_type = "CUSTOMER"

    @transaction.atomic
    def handle_request(self, phone: str):
        user, created = User.objects.get_or_create(phone=phone)

        if created:
            user.is_customer = True
            user.save(update_fields=["is_customer"])
            CustomerProfile.objects.create(user=user)
        else:
            if not user.is_customer:
                user.is_customer = True
                user.save(update_fields=["is_customer"])
                CustomerProfile.objects.get_or_create(user=user)

        create_and_send_otp(phone, self.login_type)
        return Response({"detail": "OTP sent to customer phone."})


class CustomerVerifyOTPView(BaseVerifyOTPView):
    login_type = "CUSTOMER"
    role_claim = "CUSTOMER"
    client_claim = "customer_app"

    def handle_verify(self, request, phone: str, otp_code: str):
        phone = normalize_phone(phone)
        otp_obj = self._get_latest_otp(phone)
        if not otp_obj:
            raise ValueError("OTP not found. Please request again.")

        ok, reason = otp_obj.is_valid(otp_code)
        if not ok:
            raise ValueError(reason)

        otp_obj.is_used = True
        otp_obj.save(update_fields=["is_used"])

        try:
            user = User.objects.get(phone=phone, is_customer=True)
        except User.DoesNotExist:
            raise ValueError("Customer profile not found.")

        customer = getattr(user, "customer_profile", None)
        if not customer:
            customer = CustomerProfile.objects.create(user=user)

        device_info = {
            "device_id": request.data.get("device_id", ""),
            "device_model": request.data.get("device_model", ""),
            "os_version": request.data.get("os_version", ""),
        }

        tokens = create_tokens_with_session(
            user=user,
            role=self.role_claim,
            client=self.client_claim,
            extra_claims={"customer_id": customer.id},
            device_info=device_info,
            request=request,
        )
        return Response(tokens, status=status.HTTP_200_OK)


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

    def handle_verify(self, request, phone: str, otp_code: str):
        phone = normalize_phone(phone)
        otp_obj = self._get_latest_otp(phone)
        if not otp_obj:
            raise ValueError("OTP not found. Please request again.")

        ok, reason = otp_obj.is_valid(otp_code)
        if not ok:
            raise ValueError(reason)

        otp_obj.is_used = True
        otp_obj.save(update_fields=["is_used"])

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
                "rider_id": rider.id,
                "rider_code": rider.rider_code,
            },
            device_info=device_info,
            request=request,
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

    def handle_verify(self, request, phone: str, otp_code: str):
        phone = normalize_phone(phone)
        otp_obj = self._get_latest_otp(phone)
        if not otp_obj:
            raise ValueError("OTP not found. Please request again.")

        ok, reason = otp_obj.is_valid(otp_code)
        if not ok:
            raise ValueError(reason)

        otp_obj.is_used = True
        otp_obj.save(update_fields=["is_used"])

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
                "employee_id": emp.id,
                "employee_code": emp.employee_code,
                "warehouse_code": emp.warehouse_code,
                "employee_role": emp.role,
            },
            device_info=device_info,
            request=request,
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
            request=request,
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

        user, created = User.objects.get_or_create(
            phone=phone, defaults={"full_name": full_name}
        )
        if not created and user.full_name != full_name:
            user.full_name = full_name
        user.is_rider = True
        user.save(update_fields=["is_rider", "full_name"])

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

        user, created = User.objects.get_or_create(
            phone=phone, defaults={"full_name": full_name}
        )
        if not created and user.full_name != full_name:
            user.full_name = full_name
        user.is_employee = True
        user.save(update_fields=["is_employee", "full_name"])

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
        return Response({"detail": "Employee status updated."})
