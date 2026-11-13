from rest_framework import status
from rest_framework.test import APIClient


# Tests for api/matchmaking/check_if_banned/
def test_CheckTemporaryBanAPIView_user_with_active_ban(test_player_a, test_temporary_ban_player_a_for_30min):
    client = APIClient()
    client.force_authenticate(user=test_player_a)
    response = client.get("/api/matchmaking/check_if_banned/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["banned"]
    assert response.data["expires_at"] == test_temporary_ban_player_a_for_30min.expires_at.isoformat(timespec="seconds")


def test_CheckTemporaryBanAPIView_user_without_active_ban(test_player_a):
    client = APIClient()
    client.force_authenticate(user=test_player_a)
    response = client.get("/api/matchmaking/check_if_banned/")
    assert response.status_code == status.HTTP_200_OK
    assert not response.data["banned"]
    assert not response.data["expires_at"]


def test_CheckTemporaryBanAPIView_requires_authentication():
    client = APIClient()
    response = client.get("/api/matchmaking/check_if_banned/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
