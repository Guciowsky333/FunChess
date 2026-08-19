from django.db import transaction
from rest_framework import serializers

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
