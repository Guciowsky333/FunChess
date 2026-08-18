from rest_framework import serializers

from accounts.models import CustomUser, VerificationCode
from accounts.validators import validate_passwords


class SendVerificationCodeSerializer(serializers.Serializer):
    password = serializers.CharField(required=True, write_only=True)
    password_2 = serializers.CharField(required=True, write_only=True)
    email = serializers.EmailField(required=True)

    def validate(self, data):
        password = data["password"]
        password_2 = data["password_2"]
        email = data["email"]

        validate_passwords(password, password_2)

        if CustomUser.objects.filter(email=email).exists():
            raise serializers.ValidationError("User with this email already exists")
        if VerificationCode.objects.filter(email=email).exists():
            raise serializers.ValidationError("We have already sent a verification code to this email")

        return data
