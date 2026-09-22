import json
from datetime import timedelta

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.utils import timezone

from config.asgi import application
from games.models import Game


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_connect_as_white_player(test_game_status_waiting, access_token_white):
    communicator = WebsocketCommunicator(
        application,
        f"/ws/games/{test_game_status_waiting.id}/",
        headers=[(b"cookie", f"access_token={access_token_white}".encode())],
    )
    connected, subprotocol = await communicator.connect()
    assert communicator.scope["user"] == test_game_status_waiting.white_player
    assert connected
    await database_sync_to_async(test_game_status_waiting.refresh_from_db)()
    assert test_game_status_waiting.white_connected
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_connect_as_black_player(test_game_status_waiting, access_token_black):
    communicator = WebsocketCommunicator(
        application,
        f"/ws/games/{test_game_status_waiting.id}/",
        headers=[(b"cookie", f"access_token={access_token_black}".encode())],
    )

    connected, subprotocol = await communicator.connect()
    assert communicator.scope["user"] == test_game_status_waiting.black_player
    assert connected
    await database_sync_to_async(test_game_status_waiting.refresh_from_db)()
    assert test_game_status_waiting.black_connected
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_connect_as_user_not_belongs_to_game(
    test_game_status_waiting, test_user_not_belongs_to_game, access_token_user_not_belongs_to_game
):
    communicator = WebsocketCommunicator(
        application,
        f"/ws/games/{test_game_status_waiting.id}/",
        headers=[(b"cookie", f"access_token={access_token_user_not_belongs_to_game}".encode())],
    )

    connected, subprotocol = await communicator.connect()
    assert connected

    response = await communicator.receive_json_from()
    assert communicator.scope["user"] == test_user_not_belongs_to_game
    assert response["error"] == "You do not belong to this game"
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_connect_user_provided_not_exist_game(test_user_1, access_token):
    communicator = WebsocketCommunicator(
        application,
        "/ws/games/9999/",
        headers=[(b"cookie", f"access_token={access_token}".encode())],
    )
    connected, subprotocol = await communicator.connect()
    assert communicator.scope["user"] == test_user_1
    assert connected
    response = await communicator.receive_json_from()
    assert response["error"] == "Game not found"
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_connect_both_players(test_game_status_waiting, access_token_black):
    """
    In this test we change filed "white_connected" manually in provided game
    and expect that when black player will connect status and current_turn_started_at
    will change at provided game
    """
    test_game_status_waiting.white_connected = True
    await database_sync_to_async(test_game_status_waiting.save)()
    communicator = WebsocketCommunicator(
        application,
        f"/ws/games/{test_game_status_waiting.id}/",
        headers=[(b"cookie", f"access_token={access_token_black}".encode())],
    )
    connected, subprotocol = await communicator.connect()
    assert communicator.scope["user"] == test_game_status_waiting.black_player
    assert connected
    await database_sync_to_async(test_game_status_waiting.refresh_from_db)()
    assert test_game_status_waiting.black_connected
    assert test_game_status_waiting.status == Game.Status.IN_PROGRESS
    assert test_game_status_waiting.current_turn_started_at is not None


# Checking the whole flow in receive in GamesConsumer
@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_receive_resign(connected_players):
    """
    In this test we simulate case when white player resign the game, and we expected
    that our consumer will finsh the game and update players ratings.
    White has 1200 rating black has 1000 so when white will resign the game
    black should win it and gain 24 points and white should lose 24 points.
    """
    game, white_rating, black_rating, white_communicator, black_communicator = connected_players
    await database_sync_to_async(game.refresh_from_db)()

    await white_communicator.send_to(text_data=json.dumps({"type": "resign"}))
    response = await white_communicator.receive_from()
    data = json.loads(response)
    assert data["reason"] == "surrender"

    await database_sync_to_async(game.refresh_from_db)()
    await database_sync_to_async(white_rating.refresh_from_db)()
    await database_sync_to_async(black_rating.refresh_from_db)()

    assert game.status == Game.Status.FINISHED
    assert game.result == Game.Result.BLACK_WON
    assert game.reason == Game.Reason.SURRENDER
    assert game.finished_at is not None
    assert white_rating.rating == 1200 - 24
    assert black_rating.rating == 1000 + 24


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_receive_draw_accept(connected_players):
    """
    In this test we simulate case when black player sent draw offer to white and white
    accepted it. We excepted that our consumer will finsh the game as draw and update players ratings.
    White has 1200 rating so they should lose 8 points after draw and black has 1000 so they should
    gain 8 points after draw with player with higher rating.
    """
    game, white_rating, black_rating, white_communicator, black_communicator = connected_players

    # Black player sends draw offer to his opponent
    game.draw_offered_by = Game.DrawOfferedBy.BLACK
    await database_sync_to_async(game.save)()

    await white_communicator.send_to(text_data=json.dumps({"type": "draw_accept"}))
    response = await white_communicator.receive_from()
    data = json.loads(response)

    assert data["reason"] == "draw_accepted"
    await database_sync_to_async(game.refresh_from_db)()
    await database_sync_to_async(white_rating.refresh_from_db)()
    await database_sync_to_async(black_rating.refresh_from_db)()

    assert game.status == Game.Status.FINISHED
    assert game.result == Game.Result.DRAW
    assert game.reason == Game.Reason.DRAW_ACCEPTED
    assert game.finished_at is not None

    assert white_rating.rating == 1200 - 8
    assert black_rating.rating == 1000 + 8


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_receive_white_exceeded_time(connected_players):
    """
    In this test we manually set up filed 'current_turn_started_at' in our game as game time + 1 second
    to simulate case when white player thought about firs move too long, and they exceeded time.
    We excepted that our consumer will finsh the game and update players ratings.
    White should lose the game because they exceeded time so white should lose 24 rating and black should
    gain 24 points.
    """
    game, white_rating, black_rating, white_communicator, black_communicator = connected_players
    time_control = await database_sync_to_async(lambda: game.time_control)()

    game.current_turn_started_at = timezone.now() - timedelta(seconds=(time_control.initial_time_seconds + 1))
    await database_sync_to_async(game.save)()

    # White try sends move but too late they already exceeded time
    await white_communicator.send_to(text_data=json.dumps({"type": "move", "from_square": "d2", "to_square": "d4"}))
    response = await white_communicator.receive_from()
    data = json.loads(response)
    assert data["reason"] == "timeout"

    await database_sync_to_async(game.refresh_from_db)()
    await database_sync_to_async(white_rating.refresh_from_db)()
    await database_sync_to_async(black_rating.refresh_from_db)()

    assert game.status == Game.Status.FINISHED
    assert game.result == Game.Result.BLACK_WON
    assert game.reason == Game.Reason.TIMEOUT
    assert game.finished_at is not None
    assert white_rating.rating == 1200 - 24
    assert black_rating.rating == 1000 + 24


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_receive_last_move_ended_the_game(connected_players, test_move_before_checkmate):
    """
    In this test we use 'test_move_before_checkmate' fixture that enable black player to make checkmate from square
    h4 to square f2 and black did it, and we expected that our consumer will correctly finish the game as black won
    and correctly update players ratings.
    White should lose the game because they exceeded time so white should lose 24 rating and black should
    gain 24 points.
    """
    game, white_rating, black_rating, white_communicator, black_communicator = connected_players
    await database_sync_to_async(game.save)()

    await black_communicator.send_to(text_data=json.dumps({"type": "move", "from_square": "h4", "to_square": "f2"}))
    response = await white_communicator.receive_from()
    data = json.loads(response)
    assert data["reason"] == "checkmate"

    await database_sync_to_async(game.refresh_from_db)()
    await database_sync_to_async(white_rating.refresh_from_db)()
    await database_sync_to_async(black_rating.refresh_from_db)()

    assert game.status == Game.Status.FINISHED
    assert game.result == Game.Result.BLACK_WON
    assert game.reason == Game.Reason.CHECKMATE
    assert game.finished_at is not None

    assert white_rating.rating == 1200 - 24
    assert black_rating.rating == 1000 + 24
