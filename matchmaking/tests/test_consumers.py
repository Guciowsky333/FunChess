import json

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator

from config.asgi import application
from games.models import Game


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_first_player_does_not_find_game(test_token_player_a, test_player_a, test_time_control, mocker):
    """
    Tests matchmaking when only player_a is looking for a game.
    We expect the consumer not to find an opponent and to send
    the player a message indicating that matchmaking is still in progress.
    """
    # Mocking find_opponent_with_large_range task
    mock_task = mocker.patch("matchmaking.tasks.find_opponent_with_large_range.apply_async")
    mock_task.return_value.id = "test-task-id"

    communicator = WebsocketCommunicator(
        application,
        "/ws/matchmaking/",
        headers=[(b"cookie", f"access_token={test_token_player_a}".encode())],
    )
    await communicator.connect()
    assert communicator.scope["user"] == test_player_a

    # User sends message with id of time control he wants to play
    await communicator.send_to(text_data=json.dumps({"time_control_id": test_time_control.id}))

    # No opponent is available, so the consumer informs the user that matchmaking is still in progress.
    response = await communicator.receive_from()
    data = json.loads(response)
    assert data["searching"] == "Wait still searching for your opponent"

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_two_players_find_game(
    test_token_player_a, test_token_player_b, test_time_control, test_player_a, test_player_b, mocker
):
    """
    Two players with similar ratings search for a game with the same time control.
    Expect the consumer to match them, create a Game (assigning white and black),
    and send a match_found message with the same game_id to both players.
    """

    # Mocking find_opponent_with_large_range task
    mock_task = mocker.patch("matchmaking.tasks.find_opponent_with_large_range.apply_async")
    mock_task.return_value.id = "test-task-id"

    player_a_communicator = WebsocketCommunicator(
        application,
        "/ws/matchmaking/",
        headers=[(b"cookie", f"access_token={test_token_player_a}".encode())],
    )
    player_b_communicator = WebsocketCommunicator(
        application,
        "/ws/matchmaking/",
        headers=[(b"cookie", f"access_token={test_token_player_b}".encode())],
    )

    connected_a, subprotocol_a = await player_a_communicator.connect()
    await player_b_communicator.connect()

    # First user start finding game, so far without results
    await player_a_communicator.send_to(text_data=json.dumps({"time_control_id": test_time_control.id}))
    response = await player_a_communicator.receive_from()
    data = json.loads(response)
    assert data["searching"] == "Wait still searching for your opponent"

    # Now the second player start finding game, the consumer should find player_a as opponent and create a game
    await player_b_communicator.send_to(text_data=json.dumps({"time_control_id": test_time_control.id}))

    # Expect the consumer send message with game id to both players
    response_a = await player_a_communicator.receive_from()
    data_a = json.loads(response_a)

    response_b = await player_b_communicator.receive_from()
    data_b = json.loads(response_b)

    assert data_a["type"] == "match_found" and "game_id" in data_a
    assert data_b["type"] == "match_found" and "game_id" in data_b

    # Expect that both players received the same game_id
    assert data_a["game_id"] == data_b["game_id"]

    # Checks if game has been created and the consumer choose who will play as white and who as black
    game_id = data_a["game_id"]
    game = await database_sync_to_async(
        lambda: Game.objects.select_related("white_player", "black_player", "time_control").filter(id=game_id).first()
    )()
    assert game is not None
    assert game.time_control == test_time_control
    assert game.white_player == test_player_a or game.white_player == test_player_b
    assert (
        game.black_player == test_player_a if game.white_player == test_player_b else game.black_player == test_player_b
    )

    await player_a_communicator.disconnect()
    await player_b_communicator.disconnect()
