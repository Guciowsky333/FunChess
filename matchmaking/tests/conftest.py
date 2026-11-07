import pytest
import pytest_asyncio
from channels.testing import WebsocketCommunicator
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import CustomUser
from config.asgi import application
from games.models import Game, TimeControl
from matchmaking.models import MatchmakingEntry


@pytest.fixture
def test_game(db, test_player_a, test_player_b, test_time_control):
    return Game.objects.create(
        white_player=test_player_a,
        black_player=test_player_b,
        time_control=test_time_control,
    )


@pytest.fixture
def test_time_control(db):
    return TimeControl.objects.create(category=TimeControl.Category.RAPID, initial_time_seconds=600)


@pytest.fixture
def test_player_a(db):
    return CustomUser.objects.create_user(email="player_a@com", username="test_player_a")


@pytest.fixture
def test_player_b(db):
    return CustomUser.objects.create_user(email="player_b@com", username="test_player_b")


@pytest.fixture
def test_opponent(db):
    return CustomUser.objects.create_user(email="opponent@com", username="test_opponent")


@pytest.fixture
def test_player_a_matchmaking_entry(db, test_player_a, test_time_control):
    return MatchmakingEntry.objects.create(
        user=test_player_a,
        time_control=test_time_control,
        rating=1000,
    )


@pytest.fixture
def test_token_player_a(db, test_player_a):
    return str(RefreshToken.for_user(test_player_a).access_token)


@pytest.fixture
def test_token_player_b(db, test_player_b):
    return str(RefreshToken.for_user(test_player_b).access_token)


@pytest_asyncio.fixture
async def connected_both_players(test_token_player_a, test_token_player_b):
    white_communicator = WebsocketCommunicator(
        application,
        "ws/matchmaking/",
        headers=[(b"cookie", f"access_token={test_token_player_a}".encode())],
    )
    black_communicator = WebsocketCommunicator(
        application,
        "ws/matchmaking/",
        headers=[(b"cookie", f"access_token={test_token_player_b}".encode())],
    )
    await white_communicator.connect()
    await black_communicator.connect()

    yield white_communicator, black_communicator

    await black_communicator.disconnect()
    await white_communicator.disconnect()
