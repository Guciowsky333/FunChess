from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.serializers import SendVerificationCodeSerializer
from accounts.services import create_verification_code

# Create your views here.


class SendVerificationCodeAPIView(APIView):
    serializer_class = SendVerificationCodeSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        create_verification_code(email)

        return Response(
            {
                "message": "Code has been sent to your email it will expire in 15 minutes.",
            },
            status=status.HTTP_200_OK,
        )
