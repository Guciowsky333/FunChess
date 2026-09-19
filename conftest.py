import pytest

from accounts.models import CustomUser


@pytest.fixture
def test_user_1(db):
    return CustomUser.objects.create_user(email="testuser@test1.com", username="test_username_1")


@pytest.fixture
def test_user_2(db):
    return CustomUser.objects.create_user(email="testuser@test2.com", username="test_username_2")
