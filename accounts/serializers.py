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


class CreateCustomUserSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True)
    password_2 = serializers.CharField(required=True, write_only=True)
    username = serializers.CharField(required=True)
    code = serializers.CharField(required=True, write_only=True, max_length=6)

    def validate(self, data):
        password = data["password"]
        password_2 = data["password_2"]
        email = data["email"]
        username = data["username"]

        validate_passwords(password, password_2)

        if CustomUser.objects.filter(email=email).exists():
            raise serializers.ValidationError("User with this email already exists")

        if CustomUser.objects.filter(username=username).exists():
            raise serializers.ValidationError("User with this username already exists")

        return data


class GoogleOAuth2Serializer(serializers.Serializer):
    google_token = serializers.CharField(required=True, write_only=True)
    username = serializers.CharField(required=False)


class ChangeAvatarSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ["avatar"]


class SentResetPasswordCodeSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate_email(self, email):
        if not CustomUser.objects.filter(email=email).exists():
            raise serializers.ValidationError("User with provided email does not exist")
        if VerificationCode.objects.filter(email=email).exists():
            raise serializers.ValidationError("We have already sent a verification code to this email")

        return email


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    new_password = serializers.CharField(required=True, write_only=True)
    new_password_2 = serializers.CharField(required=True, write_only=True)
    code = serializers.CharField(required=True, write_only=True, max_length=6)

    def validate(self, data):
        new_password = data["new_password"]
        new_password_2 = data["new_password_2"]

        validate_passwords(new_password, new_password_2)

        return data
