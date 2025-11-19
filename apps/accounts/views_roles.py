from rest_framework.views import APIView
from rest_framework.response import Response
from .models import User
from .permissions import IsAdmin

class ChangeUserRole(APIView):
    permission_classes = [IsAdmin]

    def post(self, request):
        user_id = request.data["user_id"]
        role = request.data["role"]

        user = User.objects.get(id=user_id)
        user.app_role = role
        user.save()

        return Response({"message": "Role updated", "role": role})
