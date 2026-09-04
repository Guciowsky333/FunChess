from datetime import timedelta

import pytest
from django.utils import timezone

from games.exceptions import (
    DrawOfferAlreadyExists,
    DrawOfferNotFound,
    ExceededTimeError,
    IllegalChessMove,
    InvalidAction,
    InvalidMoveFormat,
    NotOpponentDrawOffer,
)
from games.models import Game, Move
from games.services import check_or_update_time, get_current_turn_player, process_move, validate_action


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"type": "move", "from_square": "e2", "to_square": "e4"}, id="Move type"),
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
            {"type": "move", "from_square": "e2", "to_square": "e4", "additional_key": "x"},
            InvalidAction,
            id="Move type with additional keys in body",
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


def test_check_or_update_time(test_game):
    """
    current_turn_started_at is set 10 seconds in the past, simulating that
    the given user spent 10 seconds making a move.
    Initial time is 600s, increment is 5s, so expected remaining is 600 - 10 + 5.
    """
    test_game.current_turn_started_at = timezone.now() - timedelta(seconds=10)
    check_or_update_time(test_game, test_game.white_player)
    assert test_game.white_time_remaining == 600 - 10 + 5


def test_check_or_update_time_exceed_time(test_game):
    """
    current_turn_started_at is set 601 seconds initial time is 600s so it means
    that user exceeds time, so expected that game should be over and user should lose
    """
    test_game.current_turn_started_at = timezone.now() - timedelta(seconds=601)
    with pytest.raises(ExceededTimeError):
        check_or_update_time(test_game, test_game.white_player)
    assert test_game.status == Game.Status.FINISHED
    assert test_game.result == Game.Result.BLACK_WON


def test_check_or_update_time_exceed_time_draw(test_game):
    """
    The same rules as in "test_check_or_update_time_exceed_time" but this time
    user's opponent has insufficiently chess material to deliver checkmate so the game
    should be finished as draw.
    """

    # Create chess position where white has insufficiently material
    Move.objects.create(
        game=test_game,
        player=test_game.white_player,
        ply_number=11,
        from_square="e1",
        to_square="e2",
        piece=Move.Piece.KING,
        resulting_fen="3qk3/8/8/8/8/8/8/4K3 w - - 0 1",
    )
    test_game.current_turn_started_at = timezone.now() - timedelta(seconds=601)
    with pytest.raises(ExceededTimeError):
        check_or_update_time(test_game, test_game.black_player)
    assert test_game.status == Game.Status.FINISHED
    assert test_game.result == Game.Result.DRAW


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
