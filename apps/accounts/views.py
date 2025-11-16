from django.db import transaction
from django.utils import timezone

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .models import (
    User,
    CustomerProfile,
    RiderProfile,
    EmployeeProfile,
    PhoneOTP,
    UserSession,
)
from .serializers import RequestOTPSerializer, VerifyOTPSerializer
from .utils import create_and_send_otp, normalize_phone, create_tokens_with_session
from .permissions import IsCustomer, IsRider, IsEmployee


# ========== Base OTP Views ==========

class BaseRequestOTPView(APIView):
    login_type = None  # "CUSTOMER" / "RIDER" / "EMPLOYEE"

    def post(self, request, *args, **kwargs):
        serializer = RequestOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]

        try:
            return self.handle_request(phone)
        except ValueError as e:
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

        tokens = create_tokens_with_session(
            user=user,
            role=self.role_claim,
            client=self.client_claim,
            extra_claims={"customer_id": customer.id},
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

        tokens = create_tokens_with_session(
            user=user,
            role=self.role_claim,
            client=self.client_claim,
            extra_claims={
                "rider_id": rider.id,
                "rider_code": rider.rider_code,
            },
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
