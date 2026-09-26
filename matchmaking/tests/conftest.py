import pytest

from accounts.models import CustomUser
from games.models import TimeControl


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
