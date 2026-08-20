from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from accounts.serializers import CreateCustomUserSerializer, GoogleOAuth2Serializer, SendVerificationCodeSerializer
from accounts.services import create_CustomUser, create_verification_code, register_or_logg_in_with_google


# Create your views here.
class LoginRateThrottle(AnonRateThrottle):
    scope = "login"


class ThrottledTokenObtainPairView(TokenObtainPairView):
    throttle_classes = [LoginRateThrottle]

    @extend_schema(
        summary="Returns access and refresh tokens",
        description="""
        Returns access and refresh tokens for an account if credentials are valid.
        """,
        request=TokenObtainPairSerializer,
        responses={
            200: OpenApiResponse(description="Access and refresh tokens"),
            401: OpenApiResponse(description="Invalid credentials"),
            429: OpenApiResponse(description="Too Many Requests in this endpoint max per minute = 5"),
        },
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class GoogleOAuth2View(APIView):
    throttle_classes = [LoginRateThrottle]
    permission_classes = [AllowAny]
    serializer_class = GoogleOAuth2Serializer

    def post(self, request, *args, **kwargs):
        serializer = GoogleOAuth2Serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        google_token = serializer.validated_data["google_token"]
        username = serializer.validated_data.get("username")

        tokens = register_or_logg_in_with_google(google_token, username)
        return Response(tokens, status=status.HTTP_200_OK)


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


class CreateCustomUserAPIView(APIView):
    serializer_class = CreateCustomUserSerializer
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Create new account",
        description="""
            Checks whether provided code is valid and creates new account.

            Important: Users should first send request to the SendVerificationCodeAPIView endpoint to
            receive verification code in their emails but to prevent situation where users would like to 
            omit this endpoint we validate the same data here again 


            Business rules:
            - Fields email, password, password_2, username and code are required.
            - Code must be valid and not expired (valid for 15 minutes).
            - Email must be unique.
            - Email must be in valid format (validated by Django EmailField).
            - Username must be unique.
            - Fields password and password_2 must be the same.
            - Password must be at least 8 characters long.
            - Password must contain at least one uppercase letter.
            """,
        request=CreateCustomUserSerializer,
        responses={
            201: OpenApiResponse(description="Account created successfully"),
            400: OpenApiResponse(description="Validation error/ invalid code "),
        },
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        username = serializer.validated_data["username"]
        password = serializer.validated_data["password"]
        code = serializer.validated_data["code"]

        create_CustomUser(email, username, password, code)
        return Response(
            {
                "message": "Account created successfully.",
            },
            status=status.HTTP_201_CREATED,
        )
