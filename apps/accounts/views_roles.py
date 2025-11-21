# apps/accounts/views_roles.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import User
from .permissions import IsAdmin
from .serializers import ChangeUserRoleSerializer


class ChangeUserRole(APIView):
    """
    Admin panel se high-level app_role change karne ke liye.
    Ye actual domain role (CustomerProfile / RiderProfile / EmployeeProfile)
    se independent hai.
    """
    permission_classes = [IsAdmin]

    def post(self, request, user_id):
        serializer = ChangeUserRoleSerializer(
            data={'user_id': user_id, 'role': request.data.get('role')}
        )
        serializer.is_valid(raise_exception=True)

        user_id = serializer.validated_data["user_id"]
        role = serializer.validated_data["role"]

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        user.app_role = role
        user.save(update_fields=["app_role"])

        return Response(
            {"message": "Role updated", "role": role},
            status=status.HTTP_200_OK,
        )
