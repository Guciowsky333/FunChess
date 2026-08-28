import pytest
from rest_framework import serializers

from games.models import Move
from games.services import process_move


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
