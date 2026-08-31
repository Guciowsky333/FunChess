import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from games.exceptions import GameDoesNotExist, PlayerDoesNotBelongToGameError
from games.models import Game
from games.services import connect_player_to_game


@database_sync_to_async
def get_game(game_id):
    return Game.objects.select_related("white_player", "black_player").get(pk=game_id)


@database_sync_to_async
def save_game(game):
    game.save()


class GamesConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.game_id = self.scope["url_route"]["kwargs"]["game_id"]
        self.game_group_name = f"game_{self.game_id}"
        user = self.scope["user"]
        try:
            await connect_player_to_game(self.game_id, user)
            await self.channel_layer.group_add(self.game_group_name, self.channel_name)
            await self.accept()
        except GameDoesNotExist:
            await self.accept()
            await self.send(text_data=json.dumps({"error": "Game not found"}))
            await self.close()
            return
        except PlayerDoesNotBelongToGameError:
            await self.accept()
            await self.send(text_data=json.dumps({"error": "You do not belong to this game"}))
            await self.close()
            return

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.game_group_name, self.channel_name)

    async def receive(self, text_data):
        pass
