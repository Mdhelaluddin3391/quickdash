# apps/accounts/views_onboarding.py
from django.contrib.auth import get_user_model
from rest_framework import status, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import RiderProfile, EmployeeProfile
from .permissions import IsAdmin
from .serializers import (
    AdminCreateRiderSerializer,
    AdminCreateEmployeeSerializer,
    AdminChangeEmployeeStatusSerializer,
    RiderAdminListSerializer,
    EmployeeAdminListSerializer,
)
from .utils import normalize_phone

User = get_user_model()


# ==========================
# RIDER ONBOARDING (CUSTOMER SIDE)
# ==========================

class RiderApplyView(views.APIView):
    """
    Rider apply API:
    - User pehle normal CUSTOMER login kare (OTP se)
    - Phir yeh endpoint call kare (JWT required)
    - RiderProfile PENDING state me banega / update hoga
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        vehicle_type = request.data.get("vehicle_type", "").strip() or None

        profile, created = RiderProfile.objects.get_or_create(
            user=user,
            defaults={
                "rider_code": f"RIDER-{user.id.hex[:8].upper()}" if hasattr(user, "id") else "",
                "vehicle_type": vehicle_type,
            },
        )

        # Agar pehle se hai:
        if not created:
            # Agar already approved hai:
            if profile.approval_status == RiderProfile.ApprovalStatus.APPROVED:
                return Response(
                    {
                        "detail": "You are already an approved rider.",
                        "status": profile.approval_status,
                    },
                    status=status.HTTP_200_OK,
                )
            # Pending / rejected ho to latest info update kar do
            if vehicle_type:
                profile.vehicle_type = vehicle_type
            profile.save()

        return Response(
            {
                "detail": "Rider application submitted. Admin will review.",
                "approval_status": profile.approval_status,
            },
            status=status.HTTP_200_OK,
        )


# ==========================
# ADMIN: RIDER MANAGEMENT
# ==========================

class AdminRiderListView(views.APIView):
    """
    Admin ke liye:
    GET /admin/riders/?approval_status=PENDING/APPROVED/REJECTED (optional filter)
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        qs = RiderProfile.objects.select_related("user").all()
        status_filter = request.query_params.get("approval_status")
        if status_filter:
            qs = qs.filter(approval_status=status_filter)

        data = RiderAdminListSerializer(qs, many=True).data
        return Response(data)


class AdminApproveRiderView(views.APIView):
    """
    POST /admin/riders/<int:pk>/approve/
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, pk):
        try:
            profile = RiderProfile.objects.select_related("user").get(pk=pk)
        except RiderProfile.DoesNotExist:
            return Response(
                {"detail": "Rider not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        profile.approval_status = RiderProfile.ApprovalStatus.APPROVED
        profile.status = RiderProfile.RiderStatus.ACTIVE
        profile.save(update_fields=["approval_status", "status"])

        return Response(
            {"detail": "Rider approved.", "status": profile.status},
            status=status.HTTP_200_OK,
        )


class AdminRejectRiderView(views.APIView):
    """
    POST /admin/riders/<int:pk>/reject/
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, pk):
        try:
            profile = RiderProfile.objects.select_related("user").get(pk=pk)
        except RiderProfile.DoesNotExist:
            return Response(
                {"detail": "Rider not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        profile.approval_status = RiderProfile.ApprovalStatus.REJECTED
        profile.status = RiderProfile.RiderStatus.SUSPENDED
        profile.save(update_fields=["approval_status", "status"])

        return Response(
            {"detail": "Rider rejected."},
            status=status.HTTP_200_OK,
        )


# ==========================
# ADMIN: EMPLOYEE HR APIs
# ==========================

class AdminEmployeeListCreateView(views.APIView):
    """
    GET  /admin/employees/      -> list all employees
    POST /admin/employees/      -> HR create employee
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        qs = EmployeeProfile.objects.select_related("user").all()
        data = EmployeeAdminListSerializer(qs, many=True).data
        return Response(data)

    def post(self, request):
        serializer = AdminCreateEmployeeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = normalize_phone(serializer.validated_data["phone"])
        full_name = serializer.validated_data["full_name"]
        employee_code = serializer.validated_data["employee_code"]
        role = serializer.validated_data["role"]
        warehouse_code = serializer.validated_data["warehouse_code"]

        user, created = User.objects.get_or_create(phone=phone)
        if full_name and user.full_name != full_name:
            user.full_name = full_name

        # Agar already employee hai to error
        if hasattr(user, "employee_profile"):
            return Response(
                {"detail": "Employee already exists for this phone."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        profile = EmployeeProfile.objects.create(
            user=user,
            employee_code=employee_code,
            role=role,
            warehouse_code=warehouse_code,
        )

        # (optional) boolean flag update, agar tumne model me field add kiya ho
        if hasattr(user, "is_employee"):
            user.is_employee = True
        user.save()

        data = EmployeeAdminListSerializer(profile).data
        return Response(data, status=status.HTTP_201_CREATED)


class AdminEmployeeStatusUpdateView(views.APIView):
    """
    POST /admin/employees/<int:pk>/status/
    Body: { "status": "ACTIVE" } ya { "status": "INACTIVE" }
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, pk):
        try:
            profile = EmployeeProfile.objects.select_related("user").get(pk=pk)
        except EmployeeProfile.DoesNotExist:
            return Response(
                {"detail": "Employee not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = AdminChangeEmployeeStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        status_str = serializer.validated_data["status"].upper()

        if status_str == "ACTIVE":
            profile.is_active_employee = True
        elif status_str == "INACTIVE":
            profile.is_active_employee = False
        else:
            return Response(
                {"detail": "Invalid status. Use 'ACTIVE' or 'INACTIVE'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        profile.save(update_fields=["is_active_employee"])
        return Response(
            {"detail": "Employee status updated.", "is_active_employee": profile.is_active_employee},
            status=status.HTTP_200_OK,
        )
