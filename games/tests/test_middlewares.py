import pytest
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

from accounts.models import CustomUser
from games.middlewares import JWTAuthMiddleware


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_JWTAuthMiddleware_valid_token(access_token, test_user_1):
    received_scope = {}

    async def fake_app(scope, receive, send):
        received_scope.update(scope)

    scope = {
        "headers": [
            (b"cookie", f"access_token={access_token}".encode()),
        ]
    }
    middleware = JWTAuthMiddleware(fake_app)
    await middleware(scope, None, None)
    assert received_scope["user"] == test_user_1


@database_sync_to_async
def delete_user(user: CustomUser):
    user.delete()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_JWTAuthMiddleware_valid_token_user_does_not_exist(access_token, test_user_1):
    """
    In this test provided access token is correct but user to which this token belongs doesn't exist.
    It can happen when for instance user generated access token and then remove his account
    """

    received_scope = {}

    async def fake_app(scope, receive, send):
        received_scope.update(scope)

    scope = {
        "headers": [
            (b"cookie", f"access_token={access_token}".encode()),
        ]
    }
    # Remove user from database
    await delete_user(test_user_1)

    middleware = JWTAuthMiddleware(fake_app)
    await middleware(scope, None, None)
    assert received_scope["user"] == AnonymousUser()


@pytest.mark.parametrize(
    "headers",
    [
        pytest.param([], id="empty headers"),
        pytest.param([(b"cookie", b"other_cookie=xyz")], id="empty cookies"),
        pytest.param([(b"cookie", b"access_token=invalid_token")], id="invalid access token"),
    ],
)
@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_JWTAuthMiddleware_invalid_scope(headers):
    received_scope = {}

    async def fake_app(scope, receive, send):
        received_scope.update(scope)

    scope = {
        "headers": headers,
    }

    middleware = JWTAuthMiddleware(fake_app)
    await middleware(scope, None, None)
    assert received_scope["user"] == AnonymousUser()
