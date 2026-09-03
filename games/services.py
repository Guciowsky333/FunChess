import chess
from channels.db import database_sync_to_async
from django.utils import timezone
from rest_framework import serializers

from accounts.models import CustomUser
from games.exceptions import ExceededTimeError, GameDoesNotExist, PlayerDoesNotBelongToGameError
from games.models import Game, Move


@database_sync_to_async
def connect_player_to_game(game_id: int, user: CustomUser):
    """
    Checks if provided game exist and whether user belongs to this game.

    If user belongs to this game sets up fields "white_connected" or "black_connected"
    to "true" depending on what kind of player provided user is in this game.

    If both players are connected and the game is in WAITING status,
    changes the game status to IN_PROGRESS and sets
    "current_turn_started_at" to the current time.
    """
    try:
        game = Game.objects.select_related("white_player", "black_player").get(id=game_id)
    except Game.DoesNotExist:
        raise GameDoesNotExist

    if game.white_player == user:
        game.white_connected = True

    elif game.black_player == user:
        game.black_connected = True

    else:
        raise PlayerDoesNotBelongToGameError

    # Changes game status to IN_PROGRESS only if current game status is WAITING
    if game.white_connected and game.black_connected and game.status == Game.Status.WAITING:
        game.status = Game.Status.IN_PROGRESS
        game.current_turn_started_at = timezone.now()
    game.save()


def get_current_turn_player(game: Game) -> CustomUser:
    """
    Return user that currently has a turn.
    If the game has an even number of moves it meant that it is white's turn.
    If the game has an odds number of moves it meant that it is black's turn.
    """
    if game.moves.count() % 2 == 0:
        return game.white_player
    else:
        return game.black_player


def check_or_update_time(game: Game, user: CustomUser):
    """
    Checks if user does not exceed time limit at game.
    If yes game is over and user lose it if no subtracts time that user spend
    to make a move and add increment time if game has it.
    """

    time_spend = (timezone.now() - game.current_turn_started_at).total_seconds()

    is_white = user == game.white_player
    time_remaining = game.white_time_remaining if is_white else game.black_time_remaining

    # If user exceed time control the game is over
    if time_remaining - time_spend <= 0:
        game.status = Game.Status.FINISHED
        last_move = game.moves.order_by("-ply_number").first()

        if not last_move:
            # If it is the first move we take initial chess position
            board = chess.Board()
        else:
            # If not we take position from last move at the game
            board = chess.Board(last_move.resulting_fen)

        # Checks if user's opponent has enough material to deliver checkmate.
        # If not game result is draw. "not is_white" because we check user's opponent
        if board.has_insufficient_material(not is_white):
            game.result = Game.Result.DRAW
        else:
            game.result = Game.Result.BLACK_WON if is_white else Game.Result.WHITE_WON

        game.finished_at = timezone.now()
        game.save()
        raise ExceededTimeError

    # If user does not exceed time we set up new remaining time for user
    new_time_remaining = round((time_remaining - time_spend + game.time_control.increment_seconds), 0)
    if is_white:
        game.white_time_remaining = new_time_remaining

    else:
        game.black_time_remaining = new_time_remaining
    game.save()


def process_move(game: Game, user: CustomUser, move_uci: str) -> Move:
    """
    Checks if provided move is valid at current chess position
    (based on current fen) if yes create it.
    Also checks which player has turn right now
    """
    ply_number = game.moves.count() + 1

    # If it is the first move we take initial chess position
    if ply_number == 1:
        board = chess.Board()

    # If it is not the first move we take position from the last move at provided game
    else:
        last_move = game.moves.order_by("-ply_number").first()
        fen = last_move.resulting_fen
        board = chess.Board(fen)

    # if ply_number is odd it means that it is white player turn, and only they can make the move
    if ply_number % 2 == 1:
        if game.white_player != user:
            raise serializers.ValidationError("Now is white_player turn")

    # if ply_number is even it means that it is black player turn, and only they can make the move
    if ply_number % 2 == 0:
        if game.black_player != user:
            raise serializers.ValidationError("Now is black_player turn")

    try:
        move = chess.Move.from_uci(move_uci)
    except (ValueError, chess.InvalidMoveError):
        raise serializers.ValidationError("Invalid move format")

    # Checks if the move is illegal
    if move not in board.legal_moves:
        raise serializers.ValidationError("Illegal chess move")

    from_square = chess.square_name(move.from_square)
    to_square = chess.square_name(move.to_square)
    piece = (board.piece_at(move.from_square)).symbol().upper()
    promotion = chess.piece_symbol(move.promotion).upper() if move.promotion else None
    board.push(move)
    resulting_fen = board.fen()

    return Move.objects.create(
        game=game,
        player=user,
        ply_number=ply_number,
        from_square=from_square,
        to_square=to_square,
        piece=piece,
        promotion=promotion,
        resulting_fen=resulting_fen,
    )
