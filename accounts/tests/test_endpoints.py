import pytest
from rest_framework import status
from rest_framework.test import APIClient

# Tests for /api/accounts/send_verification_code/


@pytest.mark.django_db
def test_SendVerificationCodeAPIView():
    client = APIClient()
    body = {"password": "Test_password", "password_2": "Test_password", "email": "test1@test1.com"}
    response = client.post("/api/accounts/send_verification_code/", body)
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.parametrize(
    "payload, expected_status",
    [
        # Too short password
        ({"password": "Short", "password_2": "Short", "email": "test1@test1.com"}, status.HTTP_400_BAD_REQUEST),
        # Password does not contain uppercase later
        (
            {"password": "without_uppercase", "password_2": "without_uppercase", "email": "test1@test1.com"},
            status.HTTP_400_BAD_REQUEST,
        ),
        # Passwords dont match
        (
            {"password": "Password_1", "password_2": "Password_2", "email": "test1@test1.com"},
            status.HTTP_400_BAD_REQUEST,
        ),
        # Invalid email format
        (
            {"password": "Test_password", "password_2": "Test_password", "email": "invalid_email_format"},
            status.HTTP_400_BAD_REQUEST,
        ),
        # User with provided email already exist test_user has this email
        (
            {"password": "Test_password", "password_2": "Test_password", "email": "testuser1@test1.com"},
            status.HTTP_400_BAD_REQUEST,
        ),
        # Verification code has already been sent to the provided email
        (
            {"password": "Test_password", "password_2": "Test_password", "email": "testuser@test.com"},
            status.HTTP_400_BAD_REQUEST,
        ),
    ],
)
@pytest.mark.django_db
def test_SendVerificationCodeAPIView_invalid_data(payload, expected_status, test_user, test_verification_code):
    client = APIClient()
    response = client.post("/api/accounts/send_verification_code/", payload)
    assert response.status_code == expected_status
