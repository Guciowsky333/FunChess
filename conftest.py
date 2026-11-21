import pytest

from accounts.models import CustomUser
from config.celery import app
from games.models import TimeControl


@pytest.fixture(autouse=True)
def celery_eager():
    app.conf.task_always_eager = True
    app.conf.task_eager_propagates = True


@pytest.fixture
def test_user_1(db):
    return CustomUser.objects.create_user(email="testuser@test1.com", username="test_username_1")


@pytest.fixture
def test_user_2(db):
    return CustomUser.objects.create_user(email="testuser@test2.com", username="test_username_2")


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
