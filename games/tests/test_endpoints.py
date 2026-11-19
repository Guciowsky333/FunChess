from rest_framework import status
from rest_framework.test import APIClient

# Test for /api/games/history/me/


def test_MyGameHistoryView(test_player_a, test_player_a_game_1_day_ago, test_player_a_game_2_day_ago):
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


def test_MyGameHistoryView_requires_authentication():
    client = APIClient()
    response = client.get("/api/games/history/me/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
