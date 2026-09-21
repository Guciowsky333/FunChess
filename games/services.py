import chess
from channels.db import database_sync_to_async
from django.db import transaction
from django.utils import timezone

from accounts.models import CustomUser
from games.exceptions import (
    DrawOfferAlreadyExists,
    DrawOfferNotFound,
    GameDoesNotExist,
    IllegalChessMove,
    InvalidAction,
    InvalidMoveFormat,
    NotOpponentDrawOffer,
    PlayerDoesNotBelongToGameError,
    TheGameIsFinished,
    TheGameIsNotOver,
    TooLongMessage,
)
from games.models import ChatMessage, Game, Move, UserRating
from games.tasks import check_opponent_time


# Functions use in consumers.py connect
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

    if game.status == Game.Status.FINISHED:
        raise TheGameIsFinished
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
        # call task than start count white time
        task = check_opponent_time.apply_async(
            args=[game_id, 0],
            countdown=game.white_time_remaining,
        )
        game.pending_timeout_task_id = task.id

    game.save()


# Functions use in consumers.py receive
def validate_action(body: dict, game: Game, user: CustomUser) -> dict:
    """
    Players can send six types of requests to the server during a game:

    - move: The player wants to make a move. Requires "from_square" and
      "to_square" fields.
    - resign: The player wants to resign the game. No additional fields
      are required.
    - draw_offer: The player wants to offer a draw to the opponent.
      The "draw_offered_by" field in the game must be None.
      No additional fields are required.
    - draw_accept: The player who received a draw offer accepts it.
      The "draw_offered_by" field in the game must contain the opponent's
      color. No additional fields are required.
    - draw_reject: The player who received a draw offer rejects it.
      The "draw_offered_by" field in the game must contain the opponent's
      color. No additional fields are required.
    - chat: The player wants to send a chat message to the opponent.
      The "text" field is required.

    Important: This function does not create or changes anything it only valid types and then others
    functions will manage this types and do rest.
    """

    # Checks body format
    if not isinstance(body, dict):
        raise InvalidAction

    if not isinstance(body.get("type"), str):
        raise InvalidAction

    action_type = body["type"].lower()

    allowed_type = ("move", "resign", "draw_offer", "draw_accept", "draw_reject", "chat")
    if action_type not in allowed_type:
        raise InvalidAction

    # If type is move fields "from_square" and "to_square" are required
    if action_type == "move":
        if "from_square" not in body or "to_square" not in body:
            raise InvalidAction
        if not body["from_square"] or not body["to_square"]:
            raise InvalidAction

        # Type move also enable plyer to make promotion allowed (N-Knight, B-Bishop, R-Rook, Q-Queen)
        # Field promotion is not required
        if "promotion" in body:
            if body["promotion"].upper() not in ("N", "B", "R", "Q"):
                raise InvalidAction

    if action_type == "chat":
        # budy must contain type amd text
        if len(body) != 2:
            raise InvalidAction
        if "text" not in body:
            raise InvalidAction
        if not body["text"]:
            raise InvalidAction
        if len(body["text"]) > 500:
            raise TooLongMessage

    # In this types body must contain only type filed
    if action_type in ("resign", "draw_offer", "draw_accept", "draw_reject"):
        if len(body) != 1:
            raise InvalidAction

    # Field "draw_offered_by" must be None if the player want offer draw to the opponent
    if action_type == "draw_offer":
        if game.draw_offered_by:
            raise DrawOfferAlreadyExists

    # Checks if filed "draw_offered_by" is user's opponent's color
    if action_type in ("draw_accept", "draw_reject"):
        if not game.draw_offered_by:
            raise DrawOfferNotFound
        is_white = user == game.white_player
        if is_white:
            if game.draw_offered_by == game.DrawOfferedBy.WHITE:
                raise NotOpponentDrawOffer
        else:
            if game.draw_offered_by == game.DrawOfferedBy.BLACK:
                raise NotOpponentDrawOffer

    return body


def create_chat_message(message: str, game: Game, user: CustomUser) -> None:
    """
    Creates ChatMessage modle inside the game.
    """
    ChatMessage.objects.create(
        message=message,
        game=game,
        user=user,
    )


def surrender_the_game(game: Game, user: CustomUser) -> None:
    """
    Finish the game, player who sent body with "resign" type lost it.
    """
    game.status = Game.Status.FINISHED
    game.finished_at = timezone.now()
    # checks player's color
    is_white = user == game.white_player
    # Player's opponent win the game
    game.result = Game.Result.BLACK_WON if is_white else Game.Result.WHITE_WON
    game.reason = Game.Reason.SURRENDER
    game.save()

    # Updates players ratings
    change_players_ratings_after_game(game)


def draw_offer(game: Game, user: CustomUser) -> None:
    """
    Sets up filed "draw_offered_by" in the game as player's color who sent body with "draw_offer" type.
    """
    is_white = user == game.white_player
    game.draw_offered_by = game.DrawOfferedBy.WHITE if is_white else game.DrawOfferedBy.BLACK
    game.save()


def draw_accept(game: Game) -> None:
    """
    Finishes the game as draw. Assumes the accepting player and the
    existence of a pending draw offer have already been validated
    in validate_action.
    """
    game.status = Game.Status.FINISHED
    game.result = Game.Result.DRAW
    game.reason = Game.Reason.DRAW_ACCEPTED
    game.finished_at = timezone.now()
    game.save()

    # Updates players ratings
    change_players_ratings_after_game(game)


def draw_reject(game: Game) -> None:
    """
    Sets up filed "draw_offered_by" again as "None". Assumes that rejecting
    player and if he is able to reject the draw offer have already been validated.
    in validate_action.
    """
    game.draw_offered_by = None
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


def check_or_update_time(game_id: int, user: CustomUser):
    """
    Checks if user does not exceed time limit at game.
    If yes game is over and user lose it if no subtracts time that user spend
    to make a move and add increment time if game has it.
    """
    with transaction.atomic():
        # Uses transaction atomic here to prevent double check time by celery task "check_opponent_time" and this function
        game = Game.objects.select_for_update().get(id=game_id)

        # If the game has different status that IN_PROGRESS it means that our
        # task has already finished it and updated players ratings so we don't need to do it agin here
        if game.status != Game.Status.IN_PROGRESS:
            raise TheGameIsFinished

        time_spend = (timezone.now() - game.current_turn_started_at).total_seconds()

        is_white = user == game.white_player
        time_remaining = game.white_time_remaining if is_white else game.black_time_remaining

        # If user exceed time control the game is over
        if time_remaining - time_spend <= 0:
            game.status = Game.Status.FINISHED
            game.reason = Game.Reason.TIMEOUT

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

            # Updates players ratings
            change_players_ratings_after_game(game)
            return

        # If user does not exceed time we set up new remaining time for user
        new_time_remaining = round((time_remaining - time_spend), 0)

        if is_white:
            game.white_time_remaining = new_time_remaining

        else:
            game.black_time_remaining = new_time_remaining
        game.save()


def process_move(game: Game, user: CustomUser, move_uci: str) -> Move:
    """
    Checks if provided move is valid at current chess position
    (based on current fen) if yes creates it, updates the mover's
    remaining time with the increment, and resets the clock for
    the opponent's upcoming turn.
    """
    ply_number = game.moves.count() + 1

    # If it is the first move we take initial chess position
    if ply_number == 1:
        board = chess.Board()

    # If it is not the first move, we take position from the last move at provided game
    else:
        last_move = game.moves.order_by("-ply_number").first()
        fen = last_move.resulting_fen
        board = chess.Board(fen)

    try:
        move = chess.Move.from_uci(move_uci)
    except (ValueError, chess.InvalidMoveError):
        raise InvalidMoveFormat

    # Checks if the move is illegal
    if move not in board.legal_moves:
        raise IllegalChessMove

    from_square = chess.square_name(move.from_square)
    to_square = chess.square_name(move.to_square)
    piece = (board.piece_at(move.from_square)).symbol().upper()
    promotion = chess.piece_symbol(move.promotion).upper() if move.promotion else None
    board.push(move)
    resulting_fen = board.fen()

    new_move = Move.objects.create(
        game=game,
        player=user,
        ply_number=ply_number,
        from_square=from_square,
        to_square=to_square,
        piece=piece,
        promotion=promotion,
        resulting_fen=resulting_fen,
    )

    # Add increment and update field "current_turn_started_at" to start count opponent's time
    increment = game.time_control.increment_seconds
    is_white = user == game.white_player
    if is_white:
        game.white_time_remaining += increment
    else:
        game.black_time_remaining += increment
    game.current_turn_started_at = timezone.now()
    game.save()

    return new_move


def check_game_end(game: Game, last_move: Move) -> str | None:
    """
    Checks if last made move does not finish the game if yes
    marks the game status as finished and correct game result if not
    it does nothing.
    """

    board = chess.Board(last_move.resulting_fen)

    # If the last move results in checkmate, the game ends with a victory for the player who made that move.
    if board.is_checkmate():
        is_white = last_move.player == game.white_player
        game.result = Game.Result.WHITE_WON if is_white else Game.Result.BLACK_WON
        game.reason = Game.Reason.CHECKMATE
        reason = "checkmate"

    # It the last move results in stalemate the game finished as draw
    elif board.is_stalemate():
        game.result = Game.Result.DRAW
        game.reason = Game.Reason.STALEMATE
        reason = "stalemate"

    # If both players don't have enough materials to deliver checkmate the game is finished as draw
    elif board.is_insufficient_material():
        game.result = Game.Result.DRAW
        game.reason = Game.Reason.INSUFFICIENT_MATERIAL
        reason = "insufficient_material"

    # If neither player moves a pawn or makes a capture for 50 full moves, the game ends in a draw.
    elif board.halfmove_clock >= 100:  # <-- 50 full moves so 100 half moves
        game.result = Game.Result.DRAW
        game.reason = Game.Reason.FIFTY_MOVE_RULE
        reason = "fifty_move_rule"

    # If players made the same chess position 3 times the game is finished as draw
    elif _has_threefold_repetition(game):
        game.result = Game.Result.DRAW
        game.reason = Game.Reason.THREEFOLD_REPETITION
        reason = "threefold_repetition_position"

    else:
        return None

    game.status = Game.Status.FINISHED
    game.finished_at = timezone.now()
    game.save()

    # Updates players ratings
    change_players_ratings_after_game(game)
    return reason


def _has_threefold_repetition(game: Game) -> bool:
    """
    Replays all moves from the game to new board and checks if players
    don't repeat the same chess position 3 times.
    """
    board = chess.Board()
    all_moves = game.moves.order_by("ply_number")
    for move in all_moves:
        move_uci = f"{move.from_square}{move.to_square}"
        if move.promotion:
            move_uci += move.promotion.lower()
        board.push(chess.Move.from_uci(move_uci))

    return board.can_claim_threefold_repetition()


def update_pending_task_id(game: Game, task_id: str) -> None:
    game.pending_timeout_task_id = task_id
    game.save()


def _calculate_elo_change(rating_a: int, rating_b: int, score_a: float, k: int = 32) -> int:
    """
    rating_a/rating_b: current Elo of both players
    score_a: 1.0 win, 0.5 draw, 0.0 loss — from player A's perspective
    Returns the rating change (+/-) to apply to player A
    """
    expected_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    return round(k * (score_a - expected_a))


def change_players_ratings_after_game(game: Game) -> None:
    """
    Uses '_calculate_elo_change' function to calculate rating that players should get after game is finished based on
    game result and players ratings, and updates rating of both players by that numbers.
    """

    if game.status != Game.Status.FINISHED:
        raise TheGameIsNotOver("The game is not over yet")
    if game.result == Game.Result.WHITE_WON:
        score_a = 1.0

    elif game.result == Game.Result.DRAW:
        score_a = 0.5

    elif game.result == Game.Result.BLACK_WON:
        score_a = 0.0

    else:
        raise ValueError("The game does not have result yet")

    game_type = game.time_control.category
    white_rating = UserRating.objects.get(user=game.white_player, category=game_type)
    black_rating = UserRating.objects.get(user=game.black_player, category=game_type)

    white_change = _calculate_elo_change(white_rating.rating, black_rating.rating, score_a)
    black_change = _calculate_elo_change(black_rating.rating, white_rating.rating, (1.0 - score_a))

    white_rating.rating += white_change
    black_rating.rating += black_change
    white_rating.save()

    black_rating.save()
