import pytest

from accounts.models import CustomUser, VerificationCode
from config.celery import app


@pytest.fixture(autouse=True)
def celery_eager():
    app.conf.task_always_eager = True
    app.conf.task_eager_propagates = True


@pytest.fixture
def test_verification_code(db):
    return VerificationCode.objects.create(
        email="testuser@test.com",
    )


@pytest.fixture
def test_user(db):
    return CustomUser.objects.create(email="testuser1@test1.com", username="test_username")
