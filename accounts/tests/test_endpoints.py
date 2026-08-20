from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import CustomUser, VerificationCode

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


# Tests for /api/accounts/create_account/


def test_CreateCustomUserAPIView(test_verification_code):
    """
    CreateCustomUserAPIView should create CustomUser object with provided data and
    delete test_verification_code
    """
    client = APIClient()
    body = {
        "password": "Test_password",
        "password_2": "Test_password",
        "email": f"{test_verification_code.email}",
        "username": "Test_username",
        "code": f"{test_verification_code.code}",
    }
    response = client.post("/api/accounts/create_account/", body)
    assert response.status_code == status.HTTP_201_CREATED
    assert CustomUser.objects.filter(email=body["email"], username=body["username"]).exists()
    assert not VerificationCode.objects.filter(id=test_verification_code.id).exists()


@pytest.mark.parametrize(
    "payload, expected_status",
    # test_verification_code has code = "test"
    # test_user has email = "testuser1@test1.com" and username = "test_username"
    [
        # Too short password
        pytest.param(
            {
                "password": "Short",
                "password_2": "Short",
                "email": "testuser@test.com",
                "username": "Test_username",
                "code": "test",
            },
            status.HTTP_400_BAD_REQUEST,
            id="too_short_password",
        ),
        # Password does not contain at least 1 uppercase
        pytest.param(
            {
                "password": "without_uppercase",
                "password_2": "without_uppercase",
                "email": "testuser@test.com",
                "username": "Test_username",
                "code": "test",
            },
            status.HTTP_400_BAD_REQUEST,
            id="password_without_uppercase",
        ),
        # Password and password_2 are not the same
        pytest.param(
            {
                "password": "Test_password",
                "password_2": "Test_password1",
                "email": "testuser@test.com",
                "username": "Test_username",
                "code": "test",
            },
            status.HTTP_400_BAD_REQUEST,
            id="passwords_not_match",
        ),
        # CustomUser with provided email already exist
        pytest.param(
            {
                "password": "Test_password",
                "password_2": "Test_password",
                "email": "testuser1@test1.com",
                "username": "Test_username",
                "code": "test",
            },
            status.HTTP_400_BAD_REQUEST,
            id="email_taken",
        ),
        # CustomUser with provided username already exist
        pytest.param(
            {
                "password": "Test_password",
                "password_2": "Test_password",
                "email": "testuser@test.com",
                "username": "test_username",
                "code": "test",
            },
            status.HTTP_400_BAD_REQUEST,
            id="username_taken",
        ),
        # Invalid code
        pytest.param(
            {
                "password": "Test_password",
                "password_2": "Test_password",
                "email": "testuser@test.com",
                "username": "Test_username",
                "code": "wrong",
            },
            status.HTTP_400_BAD_REQUEST,
            id="invalid_code",
        ),
    ],
)
def test_CreateCustomUserAPIView_invalid_data(payload, expected_status, test_verification_code, test_user):
    client = APIClient()
    response = client.post("/api/accounts/create_account/", payload)
    assert response.status_code == expected_status


# Tests for /api/accounts/google-login/
@pytest.mark.django_db
@patch("accounts.services.id_token.verify_oauth2_token")
def test_GoogleOAuth2View(mock_verify_oauth2_token):
    mock_verify_oauth2_token.return_value = {
        "email": "newuser@gmail.com",
    }
    client = APIClient()
    response = client.post(
        "/api/accounts/google-login/",
        {
            "google_token": "fake-token-doesnt-matter",
            "username": "new_username",
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert "access" and "refresh" in response.data
    assert CustomUser.objects.filter(email="newuser@gmail.com", username="new_username").exists()


@pytest.mark.django_db
@patch("accounts.services.id_token.verify_oauth2_token")
def test_GoogleOAuth2View_invalid_token(mock_verify_oauth2_token):
    mock_verify_oauth2_token.side_effect = ValueError("Invalid or expired Google token")
    client = APIClient()
    response = client.post(
        "/api/accounts/google-login/",
        {
            "google_token": "fake-token-doesnt-matter",
            "username": "new_username",
        },
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
@patch("accounts.services.id_token.verify_oauth2_token")
def test_GoogleOAuth2View_first_logg_in_without_username(mock_verify_oauth2_token):
    mock_verify_oauth2_token.return_value = {
        "email": "newuser@gmail.com",
    }
    client = APIClient()

    # Lack username in body
    response = client.post("/api/accounts/google-login/", {"google_token": "fake-token-doesnt-matter"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
@patch("accounts.services.id_token.verify_oauth2_token")
def test_GoogleOAuth2View_taken_username(mock_verify_oauth2_token, test_user):
    mock_verify_oauth2_token.return_value = {
        "email": "newuser@gmail.com",
    }
    client = APIClient()
    response = client.post(
        "/api/accounts/google-login/",
        {
            "google_token": "fake-token-doesnt-matter",
            "username": f"{test_user.username}",
        },
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
