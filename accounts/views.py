from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from accounts.serializers import (
    ChangeAvatarSerializer,
    ChangePasswordSerializer,
    CreateCustomUserSerializer,
    GoogleOAuth2Serializer,
    ResetPasswordSerializer,
    SendVerificationCodeSerializer,
    SentResetPasswordCodeSerializer,
)
from accounts.services import (
    change_password,
    create_CustomUser,
    create_verification_code,
    register_or_logg_in_with_google,
    reset_password,
)


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

    @extend_schema(
        summary="Enables users to logg in and register with Google",
        description="""
        Returns access and refresh tokens for an account if google token is valid.
        
        Business rules:
        - Field google_token is required.
        - Google token must be valid.
        - If user logg in first time username is required and it must be unique.
        """,
        request=GoogleOAuth2Serializer,
        responses={
            200: OpenApiResponse(description="Access and refresh tokens"),
            400: OpenApiResponse(description="Validation error"),
            429: OpenApiResponse(description="Too Many Requests in this endpoint max per minute = 5"),
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
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


class ChangeAvatarAPIView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ChangeAvatarSerializer

    @extend_schema(
        summary="Updates the avatar of the currently authenticated user",
        description="""
        Updates the avatar for the logged-in user's account.

        Business rules:
        - Field avatar is required.
        - Field avatar must be a valid image file (e.g. JPEG, PNG).
        - Request user must be authenticated. 
        """,
        request=ChangeAvatarSerializer,
        responses={
            200: OpenApiResponse(description="Avatar updated successfully"),
            400: OpenApiResponse(description="Validation error"),
            401: OpenApiResponse(description="Authentication credentials were not provided"),
        },
    )
    def patch(self, request):
        serializer = self.serializer_class(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "message": "Avatar changed successfully.",
            }
        )


class SendResetPasswordCodeAPIView(APIView):
    permission_classes = [AllowAny]
    serializer_class = SentResetPasswordCodeSerializer

    @extend_schema(
        summary="Send reset password code",
        description="""
        Sends verification code to user with provided email to reset password.
        Verification code will be valid for only 15 minutes.
        
        Business rules:
        - Field email is required.
        - User with provided email must exist.
        - If a verification code has been sent to the user, they cannot generate another one.
        """,
        request=SendVerificationCodeSerializer,
        responses={
            200: OpenApiResponse(description="Verification code sent successfully"),
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
            }
        )


class ResetPasswordAPIView(APIView):
    permission_classes = [AllowAny]
    serializer_class = ResetPasswordSerializer

    @extend_schema(
        summary="Sets new password",
        description="""
        This endpoint is used when users forget their passwords and want to reset it
        using a verification code sent to their emails.
            
        Important: Before using this endpoint, you must first send a request to
        SendResetPasswordCodeAPIView to receive a verification code.
        
        Business rules:
        - Field email, new_password, new_password_2 and code are required.
        - User with provided email must exist.
        - Code must be valid and associated to user's email.
        - New password must contain at least 8 characters and one uppercase letter.
        - Filed new_password and new_password_2 must be the same.
        """,
        request=ResetPasswordSerializer,
        responses={
            200: OpenApiResponse(description="New password set successfully"),
            400: OpenApiResponse(description="Validation error"),
        },
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        new_password = serializer.validated_data["new_password"]
        code = serializer.validated_data["code"]
        reset_password(new_password, email, code)
        return Response(
            {
                "message": "Password has been reset successfully.",
            }
        )


class ChangePasswordAPIView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    @extend_schema(
        summary="Change password",
        description="""
        Change password of request user to a new one if they provided the correct old password.
        
        Business rules:
        - Field old_password, new_password, new_password_2 are required.
        - Old password must be the same as current request user password.
        - New password cannot be the same as old password.
        - New password must contain at least 8 characters and one uppercase letter.
        - Filed new_password and new_password_2 must be the same.
        - Request user must be authenticated.
        """,
        request=ChangePasswordSerializer,
        responses={
            200: OpenApiResponse(description="New password changed successfully"),
            400: OpenApiResponse(description="Validation error"),
            401: OpenApiResponse(description="Authentication credentials were not provided"),
        },
    )
    def patch(self, request):
        serializer = self.serializer_class(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        old_password = serializer.validated_data["old_password"]
        new_password = serializer.validated_data["new_password"]
        user = request.user
        change_password(user, old_password, new_password)
        return Response(
            {
                "message": "Password has been changed successfully.",
            }
        )
