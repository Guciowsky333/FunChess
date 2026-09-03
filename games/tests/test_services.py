from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework import serializers

from games.exceptions import ExceededTimeError
from games.models import Game, Move
from games.services import check_or_update_time, get_current_turn_player, process_move


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
    creates model Move if user provided correct first move and if they
    have turn right now.
    """
    # Only white player can make the first move
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
    # Only black player can make the move
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


def test_process_move_inappropriate_player(test_game):
    """
    It this test black player try makes first move, and we expect that
    function "process_move" return error
    """
    with pytest.raises(serializers.ValidationError):
        process_move(test_game, test_game.black_player, "e2e4")
    assert not Move.objects.exists()


def test_process_move_invalid_move_format(test_game):
    with pytest.raises(serializers.ValidationError):
        process_move(test_game, test_game.white_player, "invalid_format")
    assert not Move.objects.exists()


def test_process_move_Illegal_move(test_game):
    with pytest.raises(serializers.ValidationError):
        process_move(test_game, test_game.white_player, "e2e5")
    assert not Move.objects.exists()
