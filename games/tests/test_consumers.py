import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator

from config.asgi import application
from games.models import Game


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_connect_as_white_player(test_game):
    communicator = WebsocketCommunicator(
        application,
        f"/ws/games/{test_game.id}/",
    )
    communicator.scope["user"] = test_game.white_player
    connected, subprotocol = await communicator.connect()
    assert connected
    await database_sync_to_async(test_game.refresh_from_db)()
    assert test_game.white_connected
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_connect_as_black_player(test_game):
    communicator = WebsocketCommunicator(
        application,
        f"/ws/games/{test_game.id}/",
    )
    communicator.scope["user"] = test_game.black_player
    connected, subprotocol = await communicator.connect()
    assert connected
    await database_sync_to_async(test_game.refresh_from_db)()
    assert test_game.black_connected
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_connect_as_user_not_belongs_to_game(test_game, test_user_not_belongs_to_game):
    communicator = WebsocketCommunicator(
        application,
        f"/ws/games/{test_game.id}/",
    )
    communicator.scope["user"] = test_user_not_belongs_to_game
    connected, subprotocol = await communicator.connect()
    assert connected

    response = await communicator.receive_json_from()
    assert response["error"] == "You do not belong to this game"
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_connect_user_provided_not_exist_game(test_user_1):
    communicator = WebsocketCommunicator(
        application,
        "/ws/games/9999/",
    )
    communicator.scope["user"] = test_user_1
    connected, subprotocol = await communicator.connect()
    assert connected
    response = await communicator.receive_json_from()
    assert response["error"] == "Game not found"
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_connect_both_players(test_game):
    """
    In this test we change filed "white_connected" manually in provided game
    and expect that when black player will connect status and current_turn_started_at
    will change at provided game
    """
    test_game.white_connected = True
    await database_sync_to_async(test_game.save)()
    communicator = WebsocketCommunicator(
        application,
        f"/ws/games/{test_game.id}/",
    )
    communicator.scope["user"] = test_game.black_player
    connected, subprotocol = await communicator.connect()
    assert connected
    await database_sync_to_async(test_game.refresh_from_db)()
    assert test_game.black_connected
    assert test_game.status == Game.Status.IN_PROGRESS
    assert test_game.current_turn_started_at is not None
