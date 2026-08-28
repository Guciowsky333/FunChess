from django.urls import path

from games.consumers import GamesConsumer

websocket_urlpatterns = [
    path("ws/games/<int:game_id>/", GamesConsumer.as_asgi()),
]
