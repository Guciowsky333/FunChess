from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.models import CustomUser
from games.models import Game, Move, TimeControl


@pytest.fixture
def test_user_not_belongs_to_game(db):
    return CustomUser.objects.create_user(
        email="testuser1@notbelongtogame.com", username="test_username_", password="Test_password"
    )


@pytest.fixture
def test_time_control_10_minutes(db):
    return TimeControl.objects.create(
        category=TimeControl.Category.RAPID,
        initial_time_seconds=600,
    )


@pytest.fixture
def test_time_control_increment_seconds(db):
    return TimeControl.objects.create(
        category=TimeControl.Category.RAPID,
        initial_time_seconds=180,
        increment_seconds=2,
    )


@pytest.fixture
def test_game(test_user_1, test_user_2, test_time_control_10_minutes):
    return Game.objects.create(
        white_player=test_user_1,
        black_player=test_user_2,
        time_control=test_time_control_10_minutes,
    )


@pytest.fixture
def test_game_with_set_times(test_user_1, test_user_2, test_time_control_increment_seconds):
    return Game.objects.create(
        white_player=test_user_1,
        black_player=test_user_2,
        time_control=test_time_control_increment_seconds,
        white_time_remaining=180,
        black_time_remaining=180,
        current_turn_started_at=timezone.now() - timedelta(seconds=10),
    )


@pytest.fixture
def test_move_promotion(test_game):
    return Move.objects.create(
        game=test_game,
        player=test_game.white_player,
        ply_number=8,
        piece=Move.Piece.PAWN,
        from_square="f2",
        to_square="f4",
        # Position that enable black player to promotion
        resulting_fen="rnbqkbnr/pppp1ppp/8/8/5P2/4P1P1/Pp5P/RNBQKBNR b KQkq f3 0 5",
    )
