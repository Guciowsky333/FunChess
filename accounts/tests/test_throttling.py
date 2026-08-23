from rest_framework import status
from rest_framework.test import APIClient


def test_login_throttling(test_user):
    """
    Endpoint ThrottledTokenObtainPairView has throttle rates 5 per minutes.
    In this test we send 5 requests to this endpoint and then send another one,
    which should result in a 429 error.
    """
    client = APIClient()

    for _ in range(5):
        client.post("/api/accounts/token/", {})

    # After 5 requests the next one should result in a 429 error
    response = client.get("/api/accounts/token/", {})
    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS


def test_anon_user_throttling():
    """
    Rate limiting for anonymous users is 20 per minutes.
    In this test we send 20 requests to ResetPasswordAPIView endpoint (that does
    not require authentication), and then send another one which should result in a 429 error.
    """
    client = APIClient()
    for _ in range(20):
        client.post("/api/accounts/reset_password/", {})

    response = client.post("/api/accounts/reset_password/", {})
    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS


def test_authenticated_user_throttling(test_user):
    """
    Rate limiting for authenticated users is 100 per minutes.
    In this test we send 100 requests to ChangeUsernameAPIView endpoint and then send another one,
    which should result in a 429 error.
    """
    client = APIClient()
    client.force_authenticate(test_user)
    for _ in range(100):
        client.patch("/api/accounts/change_username/", {})

    response = client.get("/api/accounts/change_username/", {})
    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
