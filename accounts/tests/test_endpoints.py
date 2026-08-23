from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

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


# Tests for /api/accounts/change_avatar/


def test_ChangeAvatarAPIView(test_image, test_user):
    client = APIClient()
    client.force_authenticate(user=test_user)
    body = {
        "avatar": test_image,
    }

    response = client.patch("/api/accounts/change_avatar/", body)
    assert response.status_code == status.HTTP_200_OK
    assert response.data["message"] == "Avatar changed successfully."


def test_ChangeAvatarAPIView_requires_authentication(test_image):
    client = APIClient()
    body = {
        "avatar": test_image,
    }

    response = client.patch("/api/accounts/change_avatar/", body)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# Test for api/accounts/send_reset_password_code/
def test_SendResetPasswordCodeAPIView(test_user):
    client = APIClient()
    body = {
        "email": test_user.email,
    }
    response = client.post("/api/accounts/send_reset_password_code/", body)
    assert response.status_code == status.HTTP_200_OK
    assert response.data["message"] == "Code has been sent to your email it will expire in 15 minutes."


def test_SendResetPasswordCodeAPIView_not_existing_email(test_user):
    client = APIClient()
    body = {
        "email": "not_existing_email@test.com",
    }
    response = client.post("/api/accounts/send_reset_password_code/", body)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_SendResetPasswordCodeAPIView_not_existing_password(test_user, test_verification_code_sent):
    """
    In this case, the test user already has a code sent to their email address, so they cannot generate another one
    """
    client = APIClient()
    body = {
        "email": test_user.email,
    }
    response = client.post("/api/accounts/send_reset_password_code/", body)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


# Test for api/accounts/reset_password/


def test_ResetPasswordAPIView(test_user, test_verification_code_sent):
    client = APIClient()
    body = {
        "email": test_user.email,
        "new_password": "New_password",
        "new_password_2": "New_password",
        "code": f"{test_verification_code_sent.code}",
    }
    response = client.post("/api/accounts/reset_password/", body)
    test_user.refresh_from_db()
    assert response.status_code == status.HTTP_200_OK
    assert response.data["message"] == "Password has been reset successfully."
    assert test_user.check_password(body["new_password"])


@pytest.mark.parametrize(
    "email_override, code_override, new_password, new_password_2, expected_status",
    [
        # All passwords errors email and code are correct
        pytest.param(None, None, "Short", "Short", status.HTTP_400_BAD_REQUEST, id="Too short password"),
        pytest.param(
            None, None, "Test_password_1", "Test_password_2", status.HTTP_400_BAD_REQUEST, id="Passwords are not match"
        ),
        pytest.param(
            None, None, "test_password", "test_password", status.HTTP_400_BAD_REQUEST, id="Password without uppercase"
        ),
        # All email or code errors passwords are correct
        pytest.param(
            "not_existing_email@test.com",
            None,
            "Test_password",
            "Test_password",
            status.HTTP_400_BAD_REQUEST,
            id="Email doesn't exist",
        ),
        pytest.param(None, "wrong", "Test_password", "Test_password", status.HTTP_400_BAD_REQUEST, id="Invalid code"),
    ],
)
def test_ResetPasswordAPIView_invalid_data(
    email_override, code_override, new_password, new_password_2, expected_status, test_user, test_verification_code_sent
):

    client = APIClient()
    body = {
        "email": email_override or test_user.email,
        "code": code_override or test_verification_code_sent.code,
        "new_password": new_password,
        "new_password_2": new_password_2,
    }
    response = client.post("/api/accounts/reset_password/", body)
    assert response.status_code == expected_status


# Test for api/accounts/change_password/
def test_ChangePasswordAPIView(test_user):
    """
    In this test test_user has password = "Test_password" and when user provided correct old_password
    endpoint should change it to a new one
    """
    client = APIClient()
    client.force_authenticate(test_user)
    body = {
        # test_user.password = "Test_password"
        "old_password": "Test_password",
        "new_password": "Test_new_password",
        "new_password_2": "Test_new_password",
    }
    response = client.patch("/api/accounts/change_password/", body)
    assert response.status_code == status.HTTP_200_OK
    assert response.data["message"] == "Password has been changed successfully."
    assert test_user.check_password(body["new_password"])


@pytest.mark.parametrize(
    # test_user.password = "Test_password"
    "payload, expected_status",
    [
        # Incorrect old password
        pytest.param(
            {
                "old_password": "incorrect_old_password",
                "new_password": "Test_new_password",
                "new_password_2": "Test_new_password",
            },
            status.HTTP_400_BAD_REQUEST,
            id="Incorrect old password",
        ),
        # New password is the same as old password
        pytest.param(
            {"old_password": "Test_password", "new_password": "Test_password", "new_password_2": "Test_password"},
            status.HTTP_400_BAD_REQUEST,
            id="New password is the same as old password",
        ),
        # New password is too short
        pytest.param(
            {"old_password": "Test_password", "new_password": "Short", "new_password_2": "Short"},
            status.HTTP_400_BAD_REQUEST,
            id="Too short new password",
        ),
        # New password without uppercase
        pytest.param(
            {
                "old_password": "Test_password",
                "new_password": "without_uppercase",
                "new_password_2": "without_uppercase",
            },
            status.HTTP_400_BAD_REQUEST,
            id="New password without uppercase",
        ),
        # Fields new_password and new_password_2 are not the same
        pytest.param(
            {
                "old_password": "Test_password",
                "new_password": "Test_new_password_1",
                "new_password_2": "Test_new_password_2",
            },
            status.HTTP_400_BAD_REQUEST,
            id="New passwords not match",
        ),
    ],
)
def test_ChangePasswordAPIView_invalid_data(payload, expected_status, test_user):
    client = APIClient()
    client.force_authenticate(test_user)
    response = client.patch("/api/accounts/change_password/", payload)
    assert response.status_code == expected_status


def test_ChangePasswordAPIView_requires_authentication():
    client = APIClient()
    response = client.patch("/api/accounts/change_password/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# Test for api/accounts/change_username/
def test_ChangeUsernameAPIView(test_user):
    client = APIClient()
    client.force_authenticate(test_user)
    body = {
        "new_username": "Test_new_username",
    }
    response = client.patch("/api/accounts/change_username/", body)
    assert response.status_code == status.HTTP_200_OK
    assert test_user.username == body["new_username"]


def test_ChangeUsernameAPIView_new_username_taken(test_user, test_user_2):
    client = APIClient()
    client.force_authenticate(test_user)
    body = {
        "new_username": f"{test_user_2.username}",
    }
    response = client.patch("/api/accounts/change_username/", body)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_ChangeUsernameAPIView_required_authentication():
    client = APIClient()
    response = client.patch("/api/accounts/change_username/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# Tests for /api/accounts/logout/
def test_LogoutAPIView(test_user):
    client = APIClient()
    client.force_authenticate(test_user)

    refresh_token = RefreshToken.for_user(test_user)
    body = {
        "refresh_token": f"{str(refresh_token)}",
    }
    response = client.post("/api/accounts/logout/", body)
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.parametrize(
    "payload, expected_status",
    [
        pytest.param(
            {"refresh_token": ""},
            status.HTTP_400_BAD_REQUEST,
            id="Empty refresh token in body",
        ),
        pytest.param(
            {"refresh_token": "Invalid"},
            status.HTTP_400_BAD_REQUEST,
            id="Invalid refresh token in body",
        ),
    ],
)
def test_LogoutAPIView_invalid_or_empty_refresh_token(payload, expected_status, test_user):
    client = APIClient()
    client.force_authenticate(test_user)
    response = client.post("/api/accounts/logout/", payload)
    assert response.status_code == expected_status


def test_LogoutAPIView_blacklisted_refresh_token(test_user):
    client = APIClient()
    client.force_authenticate(test_user)

    refresh_token = RefreshToken.for_user(test_user)
    refresh_token.blacklist()
    body = {
        "refresh_token": f"{str(refresh_token)}",
    }
    response = client.post("/api/accounts/logout/", body)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_LogoutAPIView_required_authentication():
    client = APIClient()
    response = client.get("/api/accounts/logout/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# Test for /api/accounts/me/
def test_MeAPIView(test_user):
    client = APIClient()
    client.force_authenticate(test_user)
    response = client.get("/api/accounts/me/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["username"] == test_user.username
    assert response.data["email"] == test_user.email
    assert response.data["id"] == test_user.id


def test_MeAPIView_required_authentication():
    client = APIClient()
    response = client.get("/api/accounts/me/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
