import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from matchmaking.exceptions import InvalidBody, TimeControlNotExist
from matchmaking.models import MatchmakingEntry
from matchmaking.services import search_for_match, validate_matchmaking_request
from matchmaking.tasks import find_opponent_with_large_range


def _save_pending_task_id(matchmaking_entry: MatchmakingEntry, task_id: str):
    matchmaking_entry.pending_task_id = task_id
    matchmaking_entry.save()


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

        try:
            time_control = await database_sync_to_async(validate_matchmaking_request)(body)
        except InvalidBody:
            await self.send(text_data=json.dumps({"error": "Invalid body"}))
            return
        except TimeControlNotExist:
            await self.send(text_data=json.dumps({"error": "Time control does not exist"}))
            return

        game_created, user_matchmaking_entry, game_id, user_opponent = await database_sync_to_async(search_for_match)(
            self.user, time_control
        )
        # If function find opponent and game has been created returns game_id to both players
        if game_created:
            # Sends message to user
            await self.channel_layer.group_send(
                f"matchmaking_user_{self.user.id}", {"type": "match_found", "content": {"game_id": game_id}}
            )
            # Sends message to user's opponent
            await self.channel_layer.group_send(
                f"matchmaking_user_{user_opponent}", {"type": "match_found", "content": {"game_id": game_id}}
            )
            return

        # Runs task after 60s with widnes tolerance=300
        task = await database_sync_to_async(find_opponent_with_large_range.apply_async)(
            args=[user_matchmaking_entry.id, time_control.id],
            kwargs={"tolerance": 300, "attempt": 1},
            countdown=60,
        )

        # Sets up task in user_matchmaking_entry
        await database_sync_to_async(_save_pending_task_id)(user_matchmaking_entry, task.id)
        await self.send(text_data=json.dumps({"searching": "Wait still searching for your opponent"}))
        return

    async def match_found(self, event):
        await self.send(text_data=json.dumps(event["content"]))

    async def searching(self, event):
        await self.send(text_data=json.dumps(event["content"]))
