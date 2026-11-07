from django.urls import path

from matchmaking.consumers import MatchMakingConsumer

websocket_urlpatterns = [
    path("ws/matchmaking/", MatchMakingConsumer.as_asgi()),
]
