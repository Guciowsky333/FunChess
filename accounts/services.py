from django.conf import settings
from django.db import transaction
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import CustomUser, VerificationCode
from accounts.tasks import delete_verification_code, send_verification_email


def create_verification_code(email: str) -> None:
    """
    Creates a VerificationCode model with specified email, generates code and sends this code to this email

    Important : This code will be valid only for 15 minutes after this time VerificationCode model
    with this code and email will be deleted.
    """

    verification_code = VerificationCode.objects.create(email=email)
    send_verification_email.delay(email, verification_code.code)
    delete_verification_code.apply_async(args=[verification_code.id], countdown=900)


def create_CustomUser(email: str, username: str, password: str, code: str) -> None:
    """
    Checks if provided verification code is valid and associated with provided email
    if yes creates CustomUser with provided data.

    If account has been created correctly deletes VerificationCode object.
    """
    verification_code = VerificationCode.objects.filter(email=email, code=code).first()
    if not verification_code:
        raise serializers.ValidationError("Invalid email or code")

    with transaction.atomic():
        CustomUser.objects.create(email=email, username=username, password=password)
        verification_code.delete()


def register_or_logg_in_with_google(token: str, username: str | None) -> dict[str, str]:
    """
    Returns access and refresh tokens for user who logged in or register in google API
    """

    # Checks if provided token is valid
    try:
        id_info = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except ValueError:
        raise serializers.ValidationError("Invalid or expired Google token")

    email = id_info["email"]

    user = CustomUser.objects.filter(email=email).first()

    if not user:
        # If user logg in firs time username is required
        if not username:
            raise serializers.ValidationError("Username is required when you logg in first time")
        if CustomUser.objects.filter(username=username).exists():
            raise serializers.ValidationError("Username already exists")
        user = CustomUser.objects.create(username=username, email=email)
        user.set_unusable_password()
        user.save()

    refresh = RefreshToken.for_user(user)

    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }
