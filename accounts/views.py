from drf_spectacular.utils import OpenApiResponse, extend_schema
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

    @extend_schema(
        summary="Sends verification code",
        description="""
        Sends verification code to specified email and validates passwords.

        Passwords are validated at this point to avoid sending verification email to the user
        when the provided passwords are invalid.

        Business rules:
        - Fields email, password and password_2 are required.
        - Email must be unique.
        - Email must be in valid format (validated by Django EmailField).
        - Fields password and password_2 must be the same.
        - Password must be at least 8 characters long.
        - Password must contain at least one uppercase letter.
        """,
        request=SendVerificationCodeSerializer,
        responses={
            201: OpenApiResponse(description="Verification code sent."),
            400: OpenApiResponse(description="Validation error"),
        },
    )
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
