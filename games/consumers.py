import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from games.exceptions import (
    DrawOfferAlreadyExists,
    ExceededTimeError,
    GameDoesNotExist,
    IllegalChessMove,
    InvalidAction,
    InvalidMoveFormat,
    NotOpponentDrawOffer,
    PlayerDoesNotBelongToGameError,
)
from games.models import Game
from games.services import (
    check_game_end,
    check_or_update_time,
    connect_player_to_game,
    draw_offer,
    get_current_turn_player,
    process_move,
    surrender_the_game,
    validate_action,
)
from games.tasks import check_opponent_time


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
        data = json.loads(text_data)
        game = await get_game(self.game_id)
        user = self.scope["user"]

        # Checks if player provided correct action
        try:
            body = await database_sync_to_async(validate_action)(data, game, user)
        except InvalidAction:
            await self.send(text_data=json.dumps({"error": "Invalid action"}))
            return
        except DrawOfferAlreadyExists:
            await self.send(text_data=json.dumps({"error": "Draw offer has already been sent"}))
            return
        except NotOpponentDrawOffer:
            await self.send(
                text_data=json.dumps({"error": "Your opponent didn't send draw offer,you can't accept your own offer"})
            )
            return
        # Taking player who has already turn
        current_player = await database_sync_to_async(get_current_turn_player)(game)
        if body["type"] == "resign":
            await database_sync_to_async(surrender_the_game)(game, current_player)
            await self.channel_layer.group_send(
                f"game_{self.game_id}",
                {"type": "game_ended", "content": {"result": game.result, "reason": "surrender"}},
            )
            return

        if body["type"] == "draw_offer":
            await database_sync_to_async(draw_offer)(game, current_player)
            await self.channel_layer.group_send(
                f"game_{self.game_id}",
                {"type": "draw_offered", "content": {"offered_by": self.scope["user"].id, "type": "draw_offered"}},
            )
            return

        if body["type"] == "move":
            if current_player != user:
                await self.send(text_data=json.dumps({"error": "Now is not your turn"}))
                return

            # Update player time in game
            try:
                await database_sync_to_async(check_or_update_time)(game, current_player)
            except ExceededTimeError:
                # If any player exceed time we send message to both players that the game is finished
                await self.channel_layer.group_send(
                    f"game_{self.game_id}",
                    {"type": "game_ended", "content": {"result": game.result, "reason": "timeout"}},
                )
                return

            # Checks if provided move is correct and illegal
            try:
                from_square = body["from_square"]
                to_square = body["to_square"]
                promotion = body.get("promotion", "")
                move_uci = f"{from_square}{to_square}{promotion}"
                # If everything is correct the move become the last move in the game
                last_move = await database_sync_to_async(process_move)(game, current_player, move_uci)
            except InvalidMoveFormat:
                await self.send(text_data=json.dumps({"error": "Invalid move format"}))
                return
            except IllegalChessMove:
                await self.send(text_data=json.dumps({"error": "Illegal chess move"}))
                return

            # Checks if made move does not finish the game
            await database_sync_to_async(check_game_end)(game, last_move)
            # If last move finished the game we send message to both players that the game is over
            if game.status == Game.Status.FINISHED:
                await self.channel_layer.group_send(
                    f"game_{self.game_id}",
                    {"type": "game_ended", "content": {"result": game.result, "reason": "Last move finished the game"}},
                )
                return

            # If everything is correct and last move didn't finish the game we start count opponent's time
            ply_number = last_move.ply_number
            # If White made the last move, we take Black's remaining time, and vice versa.
            is_white = current_player == game.white_player
            opponent_time_remaining = game.black_time_remaining if is_white else game.white_time_remaining
            # We run our task to prevent case when opponent does not make a move at all
            # The task will finish tha game after opponent's remaining time if they didn't make move
            check_opponent_time.apply_async(
                args=[self.game_id, ply_number],
                countdown=opponent_time_remaining,
            )

    async def game_ended(self, event):
        await self.send(text_data=json.dumps(event["content"]))
        await self.close()

    async def draw_offered(self, event):
        offered_by_id = event["content"]["offered_by"]
        if self.scope["user"].id == offered_by_id:
            return
        await self.send(text_data=json.dumps(event["content"]))
