import chess
from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.db import transaction
from django.utils import timezone

from games.models import Game
from games.services import change_players_ratings_after_game


@shared_task
def check_opponent_time(game_id: int, ply_number: int):
    """
    This task will trigger after every move during the game, and it
    checks time opponent's of player who made last move. Task will
    trigger after opponent's remaining time, and if ply_numbers in the game
    are the same it means that opponent's didn't make a move during his time so task
    automatically finish the game otherwise it does nothing.
    """
    from games.services import change_players_ratings_after_game

    with transaction.atomic():
        game = Game.objects.select_for_update().get(id=game_id)
        # The game must has status "IN_PROGRESS"
        if game.status != Game.Status.IN_PROGRESS:
            return
        number_of_moves = game.moves.count()

        # If number of moves remains unchanged the game is finished
        if number_of_moves == ply_number:
            # Checks if the opponent of the player who is run out of time has enough material to deliver checkmate
            last_move = game.moves.order_by("-ply_number").first()
            if not last_move:
                board = chess.Board()
            else:
                board = chess.Board(last_move.resulting_fen)

            # If player who still has time does not have a material the game is finished as draw
            if board.has_insufficient_material(chess.WHITE if number_of_moves % 2 == 1 else chess.BLACK):
                game.result = Game.Result.DRAW

            # If the player who has still time has enough material to deliver checkmate he is winning the game
            else:
                if number_of_moves % 2 == 1:
                    game.result = Game.Result.WHITE_WON
                else:
                    game.result = Game.Result.BLACK_WON

            game.status = Game.Status.FINISHED
            game.reason = Game.Reason.TIMEOUT
            game.finished_at = timezone.now()
            game.save()

            # Updates players ratings
            change_players_ratings_after_game(game)
            channel_layer = get_channel_layer()

            # Sending message to both player that the game is over
            async_to_sync(channel_layer.group_send)(
                f"game_{game_id}",
                {"type": "game_ended", "content": {"result": game.result, "reason": "timeout"}},
            )

        # If number of moves has been changed task does not change anything in the game
        else:
            pass


@shared_task
def check_if_user_is_still_disconnected(user_id: int, game_id: int):
    """
    This task checks if after 30s the user has returned to the game. If yes, the task does nothing.
    If not, the task ends the game as the user's loss and gives rating points to his opponent.

    Additionally: when player A disconnects and 5s later player B also disconnects, and neither of
    them returns, player B wins the game because his disconnect deadline has not expired, unlike
    player A's.

    There is also an edge case when both players disconnect at the same time (server issues, etc.).
    Instead of choosing the winner randomly (depending on which task locks the game with
    select_for_update first), the game ends as a draw.
    """

    with transaction.atomic():
        game = (
            Game.objects.select_related("white_player", "black_player").filter(id=game_id).select_for_update().first()
        )
        if game is None:
            return

        # Game has to be in progress
        if game.status != Game.Status.IN_PROGRESS:
            return

        # Checks our user's color
        is_white = game.white_player.id == user_id

        # Checks if our user is still disconnected
        if game.white_connected if is_white else game.black_connected:
            return

        game.status = Game.Status.FINISHED

        # If both players in the game exceeded disconnected_deadline it means that they both disconnected at exactly the same time
        # Otherwise opponent's tash would be first and would finish the game as opponent's loses so in this case the game is finished as DRAW
        if (
            game.white_disconnected_deadline is not None
            and game.white_disconnected_deadline <= timezone.now()
            and game.black_disconnected_deadline is not None
            and game.black_disconnected_deadline <= timezone.now()
        ):
            game.finished_at = timezone.now()
            game.result = Game.Result.DRAW

        # If only user exceeded disconnected_deadline he loses the game
        elif (
            game.white_disconnected_deadline <= timezone.now()
            if is_white
            else game.black_disconnected_deadline <= timezone.now()
        ):
            game.finished_at = timezone.now()
            game.result = Game.Result.BLACK_WON if is_white else Game.Result.WHITE_WON

        # If none of the players have exceeded disconnected_deadline task do nothing
        else:
            return

        game.save()
        change_players_ratings_after_game(game)

        # Sends message to players that the game is over
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"game_{game_id}",
            {"type": "game_ended", "content": {"result": game.result, "reason": "disconnect"}},
        )

        return
