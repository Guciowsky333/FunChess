from http.cookies import SimpleCookie

from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken


class JWTAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        headers = dict(scope["headers"])
        cookie_header = headers.get(b"cookie")

        # User must provide cookies in headers
        if not cookie_header:
            user = AnonymousUser()
        else:
            cookie = SimpleCookie()
            cookie.load(cookie_header.decode())
            access_token = cookie.get("access_token")

            # User must have saved access_token in cookies
            if not access_token:
                user = AnonymousUser()

            else:
                token = access_token.value
                jwt_auth = JWTAuthentication()
                # Validate access_token
                try:
                    validated_token = jwt_auth.get_validated_token(token.encode())
                    user = await database_sync_to_async(jwt_auth.get_user)(validated_token)
                except (InvalidToken, AuthenticationFailed):
                    print("jd")
                    user = AnonymousUser()
        scope["user"] = user
        return await self.app(scope, receive, send)
