from rest_framework.views import APIView
from rest_framework.response import Response
from .models import User
from .permissions import IsAdmin
from .serializers import ChangeUserRoleSerializer

class ChangeUserRole(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, user_id):
        serializer = ChangeUserRoleSerializer(data={'user_id': user_id, 'role': request.data.get('role')})
        serializer.is_valid(raise_exception=True)

        user_id = serializer.validated_data["user_id"]
        role = serializer.validated_data["role"]

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=404)
            
        user.app_role = role
        user.save()

        return Response({"message": "Role updated", "role": role})
