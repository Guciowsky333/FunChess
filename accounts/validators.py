from rest_framework import serializers


def validate_passwords(password: str, password_2: str) -> None:
    """
    Check if provided passwords are valid.
    Password must contain at least 8 characters and at least one uppercase letter.
    Password and password_2 must be the same.
    """
    if len(password) < 8:
        raise serializers.ValidationError("Password must be at least 8 characters")

    if not any(x.isupper() for x in password):
        raise serializers.ValidationError("Password must contain at least one uppercase letter")

    if password != password_2:
        raise serializers.ValidationError("Passwords must match")
