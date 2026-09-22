from datetime import timedelta

import pytest
from django.utils import timezone

from games.exceptions import (
    DrawOfferAlreadyExists,
    DrawOfferNotFound,
    IllegalChessMove,
    InvalidAction,
    InvalidMoveFormat,
    NotOpponentDrawOffer,
    TheGameIsNotOver,
)
from games.models import ChatMessage, Game, Move
from games.services import (
    change_players_ratings_after_game,
    check_game_end,
    check_or_update_time,
    create_chat_message,
    draw_accept,
    draw_offer,
    draw_reject,
    get_current_turn_player,
    process_move,
    surrender_the_game,
    validate_action,
)


# Tests for 'validate_action' function
@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"type": "move", "from_square": "e2", "to_square": "e4"}, id="Move type"),
        pytest.param(
            {"type": "move", "from_square": "e2", "to_square": "e4", "promotion": "q"},
            id="Move type with correct promotion Q-Queen",
        ),
        pytest.param({"type": "chat", "text": "test text"}, id="Chat type"),
        pytest.param({"type": "resign"}, id="resign type"),
        pytest.param({"type": "draw_offer"}, id="draw_offer type"),
        pytest.param({"type": "draw_accept"}, id="draw_accept type"),
        pytest.param({"type": "draw_reject"}, id="draw_reject type"),
    ],
)
def test_validate_action_valid_body(test_game, body):
    """
    In this test we check all available types in function "validate_action"
    """
    # If type is "draw_accept" or "draw_reject" we set draw_offered_by as black
    # and then call function with white player
    if body["type"] == "draw_accept" or body["type"] == "draw_reject":
        test_game.draw_offered_by = Game.DrawOfferedBy.BLACK

    result = validate_action(body, test_game, test_game.white_player)
    assert result == body


@pytest.mark.parametrize(
    "body, expected_error",
    [
        pytest.param("body is not dict", InvalidAction, id="body is not dict"),
        pytest.param({"without_type": "move"}, InvalidAction, id="Body without key 'type'"),
        pytest.param({"type": ""}, InvalidAction, id="Type is empty"),
        pytest.param({"type": "InvalidType"}, InvalidAction, id="invalid type"),
    ],
)
def test_validate_action_invalid_body_format(test_game, body, expected_error):
    with pytest.raises(expected_error):
        validate_action(body, test_game, test_game.white_player)


@pytest.mark.parametrize(
    "body, expected_error",
    [
        # type is move
        pytest.param(
            {"type": "move", "from_square": "", "to_square": ""},
            InvalidAction,
            id="Move type with empty required fields",
        ),
        pytest.param({"type": "move"}, InvalidAction, id="Move type without required fields"),
        pytest.param(
            {"type": "move", "from_square": "d2", "to_square": "d4", "promotion": "X"},
            InvalidAction,
            id="Move type with invalid promotion",
        ),
        # type is chat
        pytest.param({"type": "chat", "text": ""}, InvalidAction, id="Chat type with empty required field"),
        pytest.param({"type": "chat"}, InvalidAction, id="Chat type without required field"),
        pytest.param(
            {"type": "chat", "text": "test_text", "additional_key": "x"},
            InvalidAction,
            id="Chat type with additional keys in body",
        ),
        # type is draw_offer
        pytest.param({"type": "draw_offer"}, DrawOfferAlreadyExists, id="draw offer at the game has already been sent"),
        pytest.param(
            {"type": "draw_offer", "additional_key": "x"},
            InvalidAction,
            id="draw offer type with additional keys in body",
        ),
        # type is draw_accept
        pytest.param(
            {"type": "draw_accept", "additional_key": "x"},
            InvalidAction,
            id="Draw accept type with additional keys in body",
        ),
        pytest.param(
            {
                "type": "draw_accept",
            },
            DrawOfferNotFound,
            id="No draw offer was sent field 'draw_offered_by' in game is empty",
        ),
        pytest.param({"type": "draw_accept"}, NotOpponentDrawOffer, id="Player tries accept his own draw offer"),
        # type is draw_reject
        pytest.param(
            {"type": "draw_reject", "additional_key": "x"},
            InvalidAction,
            id="Draw reject type with additional keys in body",
        ),
        pytest.param(
            {
                "type": "draw_reject",
            },
            DrawOfferNotFound,
            id="No draw offer was sent field 'draw_offered_by' in game is empty",
        ),
        pytest.param({"type": "draw_reject"}, NotOpponentDrawOffer, id="Player tries reject his own draw offer"),
    ],
)
def test_validate_action_invalid_body(test_game, body, expected_error):
    if body["type"] == "draw_offer":
        test_game.draw_offered_by = Game.DrawOfferedBy.BLACK

    # White player first send draw_offer so 'draw_offered_by' is 'WHITE' and now tries accepts or rejects his own offer
    if body["type"] in ("draw_accept", "draw_reject") and expected_error == NotOpponentDrawOffer:
        test_game.draw_offered_by = Game.DrawOfferedBy.WHITE

    with pytest.raises(expected_error):
        validate_action(body, test_game, test_game.white_player)


# Test for 'create_chat_message' function
def test_create_chat_message(test_game):
    message = "test message"
    create_chat_message(message, test_game, test_game.white_player)

    assert ChatMessage.objects.filter(message=message, game=test_game, user=test_game.white_player).exists()


# Tests for 'surrender_the_game' function
def test_surrender_the_game_white_gave_up(test_game):
    surrender_the_game(test_game, test_game.white_player)
    assert test_game.status == Game.Status.FINISHED
    assert test_game.reason == Game.Reason.SURRENDER
    # Black should win because white conceding the game
    assert test_game.result == Game.Result.BLACK_WON
    assert test_game.finished_at is not None


def test_surrender_the_game_black_gave_up(test_game):
    surrender_the_game(test_game, test_game.black_player)
    assert test_game.status == Game.Status.FINISHED
    assert test_game.reason == Game.Reason.SURRENDER
    # White should win because black conceding the game
    assert test_game.result == Game.Result.WHITE_WON
    assert test_game.finished_at is not None


# Tests for 'draw_offer' function
def test_draw_offer_white_snet_offer(test_game):
    draw_offer(test_game, test_game.white_player)
    assert test_game.draw_offered_by == Game.DrawOfferedBy.WHITE


def test_draw_offer_black_snet_offer(test_game):
    draw_offer(test_game, test_game.black_player)
    assert test_game.draw_offered_by == Game.DrawOfferedBy.BLACK


# Test for 'draw_accept' function
def test_draw_accept(test_game):
    draw_accept(test_game)
    assert test_game.status == Game.Status.FINISHED
    assert test_game.result == Game.Result.DRAW
    assert test_game.reason == Game.Reason.DRAW_ACCEPTED
    assert test_game.finished_at is not None


# Test for 'draw_reject' function
def test_draw_reject(test_game):
    test_game.draw_offered_by = Game.DrawOfferedBy.BLACK
    draw_reject(test_game)
    assert test_game.draw_offered_by is None


# Tests for 'get_current_turn_player' function
def test_get_current_turn_player_white_turn(test_game):
    """
    test game has 0 moves so function "get_current_turn" should return
    player which play as white in this game
    """
    player = get_current_turn_player(test_game)
    assert player == test_game.white_player


def test_get_current_turn_player_black_turn(test_game):
    """
    In this test we manually create 1 move in test_game so function "get_current_turn_player"
    should return player which play as black in this game because numbers of moves in test_game
    is now odds so this mean that black has turn right now.
    """
    Move.objects.create(
        game=test_game,
        player=test_game.white_player,
        ply_number=1,
        from_square="d2",
        to_square="d4",
        piece="P",
        resulting_fen="rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq d3 0 1",
    )

    player = get_current_turn_player(test_game)
    assert player == test_game.black_player


# Tests for 'check_or_update_time' function
def test_check_or_update_time(test_game):
    """
    current_turn_started_at is set 10 seconds in the past, simulating that
    the given user spent 10 seconds making a move.
    Initial time is 600s, so expected remaining is 600 - 10.

    Important: Adding increment only when player make a move in function "process_move"
    """
    test_game.current_turn_started_at = timezone.now() - timedelta(seconds=10)
    test_game.status = Game.Status.IN_PROGRESS
    test_game.save()
    check_or_update_time(test_game.id, test_game.white_player)
    test_game.refresh_from_db()
    assert test_game.white_time_remaining == 600 - 10

    # Only after making a move, the player should receive a time increment.
    process_move(test_game, test_game.white_player, "e2e4")
    assert test_game.white_time_remaining == 590 + test_game.time_control.increment_seconds


def test_check_or_update_time_exceed_time(test_game_with_updated_ratings):
    """
    current_turn_started_at is set 601 seconds initial time is 600s so it means
    that user exceeds time, so expected that game should be over and user should lose.
    And also expected that players rating will be changed
    """
    game, white_rating, black_rating = test_game_with_updated_ratings
    game.current_turn_started_at = timezone.now() - timedelta(seconds=601)
    game.status = Game.Status.IN_PROGRESS
    game.save()

    check_or_update_time(game.id, game.white_player)
    game.refresh_from_db()
    # White had 1200 and black had 1000 when white exceeded time they should lose 24 and black should gain 24
    white_rating.refresh_from_db()
    black_rating.refresh_from_db()

    assert game.status == Game.Status.FINISHED
    assert game.reason == Game.Reason.TIMEOUT
    assert game.result == Game.Result.BLACK_WON
    assert white_rating.rating == 1200 - 24
    assert black_rating.rating == 1000 + 24


def test_check_or_update_time_exceed_time_draw(test_game_with_updated_ratings):
    """
    The same rules as in "test_check_or_update_time_exceed_time" but this time
    user's opponent has insufficiently chess material to deliver checkmate so the game
    should be finished as draw.
    """
    game, white_rating, black_rating = test_game_with_updated_ratings

    # Create chess position where white has insufficiently material
    Move.objects.create(
        game=game,
        player=game.white_player,
        ply_number=11,
        from_square="e1",
        to_square="e2",
        piece=Move.Piece.KING,
        resulting_fen="3qk3/8/8/8/8/8/8/4K3 w - - 0 1",
    )
    game.current_turn_started_at = timezone.now() - timedelta(seconds=601)
    game.status = Game.Status.IN_PROGRESS
    game.save()

    check_or_update_time(game.id, game.black_player)
    game.refresh_from_db()

    # White had 1200 and black had 1000 when white exceeded time but the game finished as drwa white should lose 8 points of rating and black should gain 8 points
    white_rating.refresh_from_db()
    black_rating.refresh_from_db()

    assert game.status == Game.Status.FINISHED
    assert game.reason == Game.Reason.TIMEOUT
    assert game.result == Game.Result.DRAW
    assert white_rating.rating == 1200 - 8
    assert black_rating.rating == 1000 + 8


# Tests for 'process_move' function


def test_process_move_valid_first_move(test_game):
    """
    In this test we check whether our function "process_move" correctly
    creates model Move if user provided correct first move.
    """

    move = process_move(test_game, test_game.white_player, "e2e4")
    assert Move.objects.filter(id=move.id).exists()
    assert move.game == test_game
    assert move.ply_number == 1
    assert move.from_square == "e2"
    assert move.to_square == "e4"
    # Pawn move
    assert move.piece == "P"


def test_process_move_valid_second_move(test_game):
    """
    In this test we manually use "process_move" function at first time
    for automatic creation first move and then check if function correctly
    take chess position from the last move.
    """
    # Create firs move
    process_move(test_game, test_game.white_player, "e2e4")

    second_move = process_move(test_game, test_game.black_player, "e7e5")
    assert second_move.game == test_game
    assert second_move.from_square == "e7"
    assert second_move.to_square == "e5"
    assert second_move.piece == "P"
    assert second_move.ply_number == 2


def test_process_move_promotion(test_game, test_move_promotion):
    """
    Fixture test_move_promotion has special fen that enable
    black player to make promotion.
    """
    promotion_move = process_move(test_game, test_game.black_player, "b2a1q")
    assert Move.objects.filter(id=promotion_move.id).exists()
    assert promotion_move.promotion == "Q"


def test_process_move_invalid_move_format(test_game):
    with pytest.raises(InvalidMoveFormat):
        process_move(test_game, test_game.white_player, "invalid_format")
    assert not Move.objects.exists()


def test_process_move_illegal_move(test_game):
    with pytest.raises(IllegalChessMove):
        process_move(test_game, test_game.white_player, "e2e5")
    assert not Move.objects.exists()


# Tests for 'check_game_end' function
def test_check_game_end_normal_move(test_game):
    """
    In this test we create first move pawn d4 and expected that
    our function "check_game_end" does nothing with our game because this move
    does not finish the game
    """
    # Sets up status as "IN_PROGRESS" because without connect in consumers.py it would be "WAITING"
    test_game.status = Game.Status.IN_PROGRESS

    normal_move = process_move(test_game, test_game.white_player, "d2d4")
    reason = check_game_end(test_game, normal_move)
    assert reason is None
    assert test_game.status == Game.Status.IN_PROGRESS
    # Game is not over
    assert test_game.result is None


def test_check_game_end_checkmate(test_game):
    """
    In this test we manually create a move that results to checkmate
    and see if our functions correctly finish game.
    """
    checkmate_move = Move.objects.create(
        game=test_game,
        player=test_game.black_player,
        ply_number=4,
        from_square="d8",
        to_square="h4",
        piece=Move.Piece.QUEEN,
        resulting_fen="rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3",
    )
    check_game_end(test_game, checkmate_move)

    assert test_game.status == Game.Status.FINISHED
    assert test_game.reason == Game.Reason.CHECKMATE
    # Player who made checkmate move is black so he should win the game
    assert test_game.result == Game.Result.BLACK_WON
    assert test_game.finished_at is not None


def test_check_game_end_stalemate(test_game):
    """
    In this test we manually create a move that result to stalemate
    and see if our functions correctly finish game.
    """
    stalemate_move = Move.objects.create(
        game=test_game,
        player=test_game.white_player,
        ply_number=1,
        from_square="b5",
        to_square="b6",
        piece=Move.Piece.QUEEN,
        resulting_fen="k7/8/1Q6/8/8/8/8/7K b - - 0 1",
    )
    check_game_end(test_game, stalemate_move)

    assert test_game.status == Game.Status.FINISHED
    assert test_game.reason == Game.Reason.STALEMATE
    assert test_game.result == Game.Result.DRAW
    assert test_game.finished_at is not None


def test_check_game_end_insufficient_material(test_game):
    """
    In this test both players has insufficient material to deliver checkmate
    so game should be finished as draw.
    """
    last_move = Move.objects.create(
        game=test_game,
        player=test_game.white_player,
        ply_number=1,
        from_square="f4",
        to_square="c1",
        piece=Move.Piece.BISHOP,
        resulting_fen="4k3/8/8/8/8/8/8/2B1K3 w - - 0 1",
    )
    check_game_end(test_game, last_move)

    assert test_game.status == Game.Status.FINISHED
    assert test_game.reason == Game.Reason.INSUFFICIENT_MATERIAL
    assert test_game.result == Game.Result.DRAW
    assert test_game.finished_at is not None


def test_check_game_end_fifty_move_rule(test_game):
    """
    The game in this test has 50 full moves without moving pawn or makes a capture
    so the game should be finished as draw.
    """
    last_move = Move.objects.create(
        game=test_game,
        player=test_game.white_player,
        ply_number=1,
        from_square="e1",
        to_square="e1",  # nieistotne dla tego testu, byle FEN był poprawny
        piece=Move.Piece.KING,
        resulting_fen="4k3/8/8/8/8/8/8/R3K3 w - - 100 60",
    )
    check_game_end(test_game, last_move)
    assert test_game.status == Game.Status.FINISHED
    assert test_game.reason == Game.Reason.FIFTY_MOVE_RULE
    assert test_game.result == Game.Result.DRAW
    assert test_game.finished_at is not None


def test_check_game_end_has_threefold_repetition(test_game):
    """
    In this test we use "process_move" function to genere first 6 moves and repeat
    the position 3 times and that should result in the game finished as draw.
    """
    moves_uci = [
        # The first full move
        "b1a3",
        "b8c6",  # <- both players move knights
        "a3b1",
        "c6b8",  # <- back into initial position
        # The second full move
        "b1a3",
        "b8c6",  # <- again the same moves
        "a3b1",
        "c6b8",
        # The third full move
        "b1a3",
        "b8c6",  # <- third time the same moves
        "a3b1",
        "c6b8",
    ]
    for ply_number, move in enumerate(moves_uci, start=1):
        if ply_number % 2 == 1:
            player = test_game.white_player
        else:
            player = test_game.black_player
        process_move(test_game, player, move)
    last_move = test_game.moves.order_by("ply_number").first()

    check_game_end(test_game, last_move)

    assert test_game.status == Game.Status.FINISHED
    assert test_game.reason == Game.Reason.THREEFOLD_REPETITION
    assert test_game.result == Game.Result.DRAW
    assert test_game.finished_at is not None


# Tests for 'change_players_ratings_after_game' function
# In all tests white players has 1200 rating and black has 1000


def test_change_players_ratings_after_game_white_won(test_game_with_updated_ratings):
    """
    When white has been won the game they should gain 8 rating points and black
    should lose 8 rating points.
    """

    game, white_rating, black_rating = test_game_with_updated_ratings
    game.result = Game.Result.WHITE_WON

    change_players_ratings_after_game(game)
    white_rating.refresh_from_db()
    black_rating.refresh_from_db()

    assert white_rating.rating == 1200 + 8
    assert black_rating.rating == 1000 - 8


def test_change_players_ratings_after_game_black_won(test_game_with_updated_ratings):
    """
    When black has been won the game they should gain 24 rating points and white
    should lose 24 rating points.
    """

    game, white_rating, black_rating = test_game_with_updated_ratings
    game.result = Game.Result.BLACK_WON

    change_players_ratings_after_game(game)
    white_rating.refresh_from_db()
    black_rating.refresh_from_db()

    assert white_rating.rating == 1200 - 24
    assert black_rating.rating == 1000 + 24


def test_change_players_ratings_after_game_draw(test_game_with_updated_ratings):
    """
    When the game has been finished as draw black should gain 8 rating points and white
    should lose 8 rating points. Because white has higher rating than black.
    """

    game, white_rating, black_rating = test_game_with_updated_ratings
    game.result = Game.Result.DRAW

    change_players_ratings_after_game(game)
    white_rating.refresh_from_db()
    black_rating.refresh_from_db()
    assert white_rating.rating == 1200 - 8
    assert black_rating.rating == 1000 + 8


@pytest.mark.parametrize(
    "game_status",
    [
        pytest.param(Game.Status.WAITING, id="The game has status 'WAITING'"),
        pytest.param(Game.Status.IN_PROGRESS, id="The game has status 'IN_PROGRESS'"),
    ],
)
def test_change_players_ratings_after_game_status_is_not_finished(test_game, game_status):
    """
    Our function 'change_players_ratings_after_game' adds ratings only when the game is over
    and has status as finished. In this test we set up status in our test_game as different that 'FINISHED'
    and expected 'TheGameIsNotOver' error.
    """

    test_game.status = game_status

    with pytest.raises(TheGameIsNotOver, match="The game is not over yet"):
        change_players_ratings_after_game(test_game)


def test_change_players_ratings_after_game_without_result(test_game):
    """
    If test_game does not have result allowed results ["WHITE_WON", "BLACK_WON", "DRAW"]
    our function should raise ValueError.
    """
    test_game.status = Game.Status.FINISHED
    test_game.result = None
    with pytest.raises(ValueError, match="The game does not have result yet"):
        change_players_ratings_after_game(test_game)
