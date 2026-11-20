from rest_framework import status
from rest_framework.test import APIClient

# Test for /api/games/history/me/


def test_history_me(test_player_a, test_player_a_game_1_day_ago, test_player_a_game_2_day_ago):
    """
    In this test our user has exactly 2 games one that he played 1 day ago and second that he played 2 days ago.
    Checking if our endpoint correctly returns all of them with all necessary fields and with correct order
    first should be 'test_player_a_game_1_day_ago' and then 'test_player_a_game_2_day_ago'
    """
    client = APIClient()
    client.force_authenticate(test_player_a)
    response = client.get("/api/games/history/me/")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    # Checking if order is correct
    assert data[0]["id"] == test_player_a_game_1_day_ago.id
    assert data[1]["id"] == test_player_a_game_2_day_ago.id

    # Checking all fields
    assert data[0]["time_control"]["id"] == test_player_a_game_1_day_ago.time_control.id
    assert data[0]["time_control"]["category"] == test_player_a_game_1_day_ago.time_control.category

    assert data[0]["result"] == test_player_a_game_1_day_ago.result
    assert data[0]["reason"] == test_player_a_game_1_day_ago.reason

    assert data[0]["white_player"]["id"] == test_player_a_game_1_day_ago.white_player.id
    assert data[0]["black_player"]["id"] == test_player_a_game_1_day_ago.black_player.id


def test_history_me_requires_authentication():
    client = APIClient()
    response = client.get("/api/games/history/me/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# Tests for # Test for /api/games/history/username/


def test_history_username(test_player_b, test_player_a, test_player_a_game_1_day_ago, test_player_a_game_2_day_ago):
    """
    Endpoint PlayerGameHistoryView is used to see others player's games history. In this test
    player_b wants to check player_a's games. Expected the endpoint return all 2 player_a's games to
    player_b in correct order.
    """
    client = APIClient()
    client.force_authenticate(test_player_b)

    response = client.get(f"/api/games/history/{test_player_a.username}/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    # Checking if order is correct
    assert data[0]["id"] == test_player_a_game_1_day_ago.id
    assert data[1]["id"] == test_player_a_game_2_day_ago.id

    # Checking all fields
    assert data[0]["time_control"]["id"] == test_player_a_game_1_day_ago.time_control.id
    assert data[0]["time_control"]["category"] == test_player_a_game_1_day_ago.time_control.category

    assert data[0]["result"] == test_player_a_game_1_day_ago.result
    assert data[0]["reason"] == test_player_a_game_1_day_ago.reason

    assert data[0]["white_player"]["id"] == test_player_a_game_1_day_ago.white_player.id
    assert data[0]["black_player"]["id"] == test_player_a_game_1_day_ago.black_player.id


def test_history_username_404(test_player_a):
    """
    The user with the name specified in the URL does not exist.
    """
    client = APIClient()
    client.force_authenticate(test_player_a)
    response = client.get("/api/games/history/not_exist_username/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_history_username_requires_authentication(test_player_a):
    client = APIClient()
    response = client.get(f"/api/games/history/{test_player_a.username}/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
