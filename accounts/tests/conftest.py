from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from accounts.models import CustomUser, VerificationCode
from config.celery import app


@pytest.fixture(autouse=True)
def celery_eager():
    app.conf.task_always_eager = True
    app.conf.task_eager_propagates = True


@pytest.fixture
def test_verification_code(db):
    return VerificationCode.objects.create(email="testuser@test.com", code="test")


@pytest.fixture
def test_user(db):
    return CustomUser.objects.create(email="testuser1@test1.com", username="test_username")


@pytest.fixture
def test_image():
    file = BytesIO()
    image = Image.new("RGB", (100, 100), color="red")
    image.save(file, "JPEG")
    file.seek(0)
    return SimpleUploadedFile("test_avatar.jpg", file.read(), content_type="image/jpeg")
