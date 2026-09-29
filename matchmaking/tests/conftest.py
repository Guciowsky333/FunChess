import pytest

from accounts.models import CustomUser
from games.models import TimeControl
from matchmaking.models import MatchmakingEntry


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
