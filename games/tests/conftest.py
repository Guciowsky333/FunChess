from unittest.mock import patch

import pytest
import pytest_asyncio
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import CustomUser
from config.asgi import application
from games.models import Game, Move, TimeControl, UserRating


@pytest.fixture
def test_user_not_belongs_to_game(db):
    return CustomUser.objects.create_user(
        email="testuser1@notbelongtogame.com", username="test_username_", password="Test_password"
    )


@pytest.fixture
def test_time_control_10_minutes(db):
    return TimeControl.objects.create(
        category=TimeControl.Category.RAPID,
        initial_time_seconds=600,
        increment_seconds=5,
    )


@pytest.fixture
def test_game(test_user_1, test_user_2, test_time_control_10_minutes):
    return Game.objects.create(
        white_player=test_user_1,
        black_player=test_user_2,
        time_control=test_time_control_10_minutes,
        white_time_remaining=600,
        black_time_remaining=600,
        status=Game.Status.IN_PROGRESS,
    )


@pytest.fixture
def test_game_status_waiting(test_user_1, test_user_2, test_time_control_10_minutes):
    return Game.objects.create(
        white_player=test_user_1,
        black_player=test_user_2,
        time_control=test_time_control_10_minutes,
        white_time_remaining=600,
        black_time_remaining=600,
    )


@pytest.fixture
def test_move_before_checkmate(test_game):
    return Move.objects.create(
        game=test_game,
        player=test_game.white_player,
        from_square="a4",
        to_square="a5",
        ply_number=7,
        piece=Move.Piece.PAWN,
        resulting_fen="rnb1k1nr/pppp1ppp/8/P1b1p3/7q/1P6/2PPPPPP/RNBQKBNR b KQkq - 0 4",
    )


@pytest.fixture
def test_move_promotion(test_game):
    return Move.objects.create(
        game=test_game,
        player=test_game.white_player,
        ply_number=8,
        piece=Move.Piece.PAWN,
        from_square="f2",
        to_square="f4",
        # Position that enable black player to promotion
        resulting_fen="rnbqkbnr/pppp1ppp/8/8/5P2/4P1P1/Pp5P/RNBQKBNR b KQkq f3 0 5",
    )


@pytest.fixture
def access_token(test_user_1):
    return str(RefreshToken.for_user(test_user_1).access_token)


@pytest.fixture
def access_token_black(test_game_status_waiting):
    black_player = test_game_status_waiting.black_player
    return str(RefreshToken.for_user(black_player).access_token)


@pytest.fixture
def access_token_white(test_game_status_waiting):
    white_player = test_game_status_waiting.white_player
    return str(RefreshToken.for_user(white_player).access_token)


@pytest.fixture
def access_token_user_not_belongs_to_game(test_user_not_belongs_to_game):
    return str(RefreshToken.for_user(test_user_not_belongs_to_game).access_token)


@pytest.fixture
def test_game_with_updated_ratings(test_game):
    """
    Changes players ratings white has 1200 and black has 1000
    """
    test_game.status = Game.Status.FINISHED

    white_rating = UserRating.objects.get(user=test_game.white_player, category=test_game.time_control.category)
    black_rating = UserRating.objects.get(user=test_game.black_player, category=test_game.time_control.category)
    white_rating.rating = 1200
    black_rating.rating = 1000

    white_rating.save()
    black_rating.save()
    test_game.save()
    return test_game, white_rating, black_rating


@pytest_asyncio.fixture
async def connected_players(test_game_with_updated_ratings, access_token_white, access_token_black):
    """
    Connects both players to the game
    """

    game, white_rating, black_rating = test_game_with_updated_ratings
    # The game must has status "WAITING"
    game.status = Game.Status.WAITING
    await database_sync_to_async(game.save)()

    with patch("games.tasks.check_opponent_time.apply_async") as mock_apply_async:
        mock_apply_async.return_value.id = "fake-task-id"

        white_communicator = WebsocketCommunicator(
            application,
            f"ws/games/{game.id}/",
            headers=[(b"cookie", f"access_token={access_token_white}".encode())],
        )
        black_communicator = WebsocketCommunicator(
            application,
            f"ws/games/{game.id}/",
            headers=[(b"cookie", f"access_token={access_token_black}".encode())],
        )
        await white_communicator.connect()
        await black_communicator.connect()

        # The game status has been changed from WAITING to IN_PROGRESS
        await database_sync_to_async(game.refresh_from_db)()

        yield game, white_rating, black_rating, white_communicator, black_communicator

        await black_communicator.disconnect()
        await white_communicator.disconnect()
