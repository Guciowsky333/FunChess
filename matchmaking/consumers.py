import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from matchmaking.exceptions import InvalidBody, TimeControlNotExist
from matchmaking.services import search_for_match, validate_matchmaking_request


class MatchMakingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        if not user.is_authenticated:
            await self.accept()
            await self.send(text_data=json.dumps({"error": "Authentication required"}))
            await self.close()
            return

        self.user = user
        await self.channel_layer.group_add(f"matchmaking_user_{user.id}", self.channel_name)
        await self.accept()

    async def disconnect(self):
        pass

    async def receive(self, text_data):

        try:
            body = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({"error": "Invalid body type"}))
            return

        # Validate time control
        try:
            time_control = await database_sync_to_async(validate_matchmaking_request)(body)
        except InvalidBody:
            await self.send(text_data=json.dumps({"error": "Invalid body type"}))
            return
        except TimeControlNotExist:
            await self.send(text_data=json.dumps({"error": "Provided time control does not exist"}))
            return

        # Taking all necessary fields from "search_for_match" function that runs all functions in services.py
        game_created, user_matchmaking_entry, game_id, user_opponent = await database_sync_to_async(search_for_match)(
            self.user, time_control
        )

    async def match_found(self, event):
        await self.send(text_data=json.dumps(event["content"]))
