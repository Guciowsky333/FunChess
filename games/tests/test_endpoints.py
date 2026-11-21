import pytest
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


# Tests filters in history endpoints


# Filter result
def test_result_only_wins(test_player_b, test_player_a, test_game_win, test_game_lose, test_game_draw):
    """
    In this test player_b checks player_a's games but only wins. Even though player_a has 3 games
    win, lose, drwa expected that the endpoint return only 1 win game.
    """
    client = APIClient()
    client.force_authenticate(test_player_b)
    response = client.get(f"/api/games/history/{test_player_a.username}/?result=win")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    # Should be only one game
    assert len(data) == 1
    assert data[0]["id"] == test_game_win.id


def test_result_only_lose(test_player_b, test_player_a, test_game_win, test_game_lose, test_game_draw):
    """
    In this test player_b checks player_a's games but only loses. Even though player_a has 3 games
    win, lose, drwa expected that the endpoint return only 1 lose game.
    """
    client = APIClient()
    client.force_authenticate(test_player_b)
    response = client.get(f"/api/games/history/{test_player_a.username}/?result=lose")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    # Should be only one game
    assert len(data) == 1
    assert data[0]["id"] == test_game_lose.id


def test_result_only_draw(test_player_b, test_player_a, test_game_win, test_game_lose, test_game_draw):
    """
    In this test player_b checks player_a's games but only draws. Even though player_a has 3 games
    win, lose, draw expected that the endpoint return only 1 draw game.
    """
    client = APIClient()
    client.force_authenticate(test_player_b)
    response = client.get(f"/api/games/history/{test_player_a.username}/?result=draw")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    # Should be only one game
    assert len(data) == 1
    assert data[0]["id"] == test_game_draw.id


def test_wrong_result(test_player_a):
    """
    Request users provided wrong result allowed results : win, lose, draw
    """
    client = APIClient()
    client.force_authenticate(test_player_a)
    response = client.get("/api/games/history/me/?result=wrong_result")
    assert response.status_code == status.HTTP_400_BAD_REQUEST


# Filter color
def test_color_white(test_player_a, test_game_white, test_game_black):
    """
    In this test our user want to see only games where he plated as white. Even though user has 2 games
    one as white and second as black expected that the endpoint return only 1 game where he played as white.
    """
    client = APIClient()
    client.force_authenticate(test_player_a)
    response = client.get("/api/games/history/me/?color=white")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == test_game_white.id


def test_color_black(test_player_a, test_game_white, test_game_black):
    """
    In this test our user want to see only games where he plated as black. Even though user has 2 games
    one as white and second as black expected that the endpoint return only 1 game where he played as black.
    """
    client = APIClient()
    client.force_authenticate(test_player_a)
    response = client.get("/api/games/history/me/?color=black")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == test_game_black.id


def test_wrong_color(test_player_a):
    """
    Request users provided wrong color allowed colors : white, black
    """
    client = APIClient()
    client.force_authenticate(test_player_a)
    response = client.get("/api/games/history/me/?color=wrong_color")
    assert response.status_code == status.HTTP_400_BAD_REQUEST


# Filter category
def test_category_bullet(test_player_a, test_game_bullet, test_game_blitz, test_game_rapid):
    """
    In this test user want to see all games but only in bullet. Even though user has 3 games
    one in bullet, one in blitz and one in rapid expected that the endpoint return only 1 game in bullet.
    """
    client = APIClient()
    client.force_authenticate(test_player_a)
    response = client.get("/api/games/history/me/?category=bullet")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == test_game_bullet.id


def test_category_blitz(test_player_a, test_game_bullet, test_game_blitz, test_game_rapid):
    """
    In this test user want to see all games but only in blitz. Even though user has 3 games
    one in bullet, one in blitz and one in rapid expected that the endpoint return only 1 game in blitz.
    """
    client = APIClient()
    client.force_authenticate(test_player_a)
    response = client.get("/api/games/history/me/?category=blitz")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == test_game_blitz.id


def test_category_rapid(test_player_a, test_game_bullet, test_game_blitz, test_game_rapid):
    """
    In this test user want to see all games but only in rapid. Even though user has 3 games
    one in bullet, one in blitz and one in rapid expected that the endpoint return only 1 game in rapid.
    """
    client = APIClient()
    client.force_authenticate(test_player_a)
    response = client.get("/api/games/history/me/?category=rapid")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == test_game_rapid.id


def test_wrong_category(test_player_a):
    """
    Request users provided wrong category allowed categories : bullet, blitz, rapid
    """
    client = APIClient()
    client.force_authenticate(test_player_a)
    response = client.get("/api/games/history/me/?category=wrong_category")
    assert response.status_code == status.HTTP_400_BAD_REQUEST


# Tests for order
@pytest.mark.parametrize(
    "order, expected_status",
    [
        pytest.param("?order=finished_at", status.HTTP_200_OK, id="Sorted games starting from the older one"),
        pytest.param("", status.HTTP_200_OK, id="Sorted games starting from the newer one by default"),
        pytest.param("?order=''", status.HTTP_400_BAD_REQUEST, id="Empty order"),
        pytest.param("?order=invalid_order", status.HTTP_400_BAD_REQUEST, id="Invalid order"),
    ],
)
def test_ordering(order, expected_status, test_player_a, test_player_a_game_1_day_ago, test_player_a_game_2_day_ago):
    client = APIClient()
    client.force_authenticate(test_player_a)
    response = client.get(f"/api/games/history/me/{order}")
    assert response.status_code == expected_status
    data = response.json()

    if order == "?order=finished_at":
        # Games should be sorted starting from the older one so test_player_a_game_2_day_ago should be first
        assert data[0]["id"] == test_player_a_game_2_day_ago.id
        assert data[1]["id"] == test_player_a_game_1_day_ago.id
    if order == "":
        # If user doesn't provide any order by default games should be sorted starting from the newest one
        # So test_player_a_game_1_day_ago should be first
        assert data[0]["id"] == test_player_a_game_1_day_ago.id
        assert data[1]["id"] == test_player_a_game_2_day_ago.id
