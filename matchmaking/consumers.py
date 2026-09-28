import json

from channels.generic.websocket import AsyncWebsocketConsumer


class MatchMakingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        if not user.is_authenticated:
            await self.accept()
            await self.send(text_data=json.dumps({"error": "Authentication required"}))
            await self.close()
            return

        self.user = user
        await self.accept()

    async def disconnect(self):
        pass

    async def receive(self, text_data):
        pass
