import chess
from celery import shared_task
from django.utils import timezone

from games.models import Game


@shared_task
def check_opponent_time(game_id: int, ply_number: int):
    """
    This task will trigger after every move during the game, and it
    checks time opponent's of player who made last move. Task will
    trigger after opponent's remaining time, and if ply_numbers in the game
    are the same it means that opponent's didn't make a move during his time so task
    automatically finish the game otherwise it does nothing.
    """

    game = Game.objects.get(id=game_id)
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

        # If the player who has still time has enough he is winning the game
        else:
            if number_of_moves % 2 == 1:
                game.result = Game.Result.WHITE_WON
            else:
                game.result = Game.Result.BLACK_WON

        game.status = Game.Status.FINISHED
        game.finished_at = timezone.now()
        game.save()

    # If number of moves has been changed task does not change anything in the game
    else:
        pass
