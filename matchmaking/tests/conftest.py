from datetime import timedelta

import pytest
import pytest_asyncio
from channels.testing import WebsocketCommunicator
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from config.asgi import application
from games.models import Game, UserRating
from matchmaking.models import MatchmakingEntry, TemporaryBan


@pytest.fixture
def test_game(db, test_player_a, test_player_b, test_time_control):
    return Game.objects.create(
        white_player=test_player_a,
        black_player=test_player_b,
        time_control=test_time_control,
        white_rating=300,
        black_rating=300,
    )


@pytest.fixture
def test_rating_player_a_1200(test_player_a, test_time_control):
    user_rating = UserRating.objects.get(user=test_player_a, category=test_time_control.category)
    user_rating.rating = 1200
    user_rating.save()
    return user_rating.rating


@pytest.fixture
def test_rating_player_b_1000(test_player_b, test_time_control):
    user_rating = UserRating.objects.get(user=test_player_b, category=test_time_control.category)
    user_rating.rating = 1000
    user_rating.save()
    return user_rating.rating


@pytest.fixture
def test_player_a_matchmaking_entry(db, test_player_a, test_time_control):
    return MatchmakingEntry.objects.create(
        user=test_player_a,
        time_control=test_time_control,
        rating=1000,
    )


@pytest.fixture
def test_temporary_ban_player_a_for_30min(db, test_player_a):
    return TemporaryBan.objects.create(
        banned_user=test_player_a,
        expires_at=timezone.now() + timedelta(minutes=30),
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
