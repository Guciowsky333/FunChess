import pytest

from games.models import Game
from matchmaking.exceptions import InvalidBody, TimeControlNotExist
from matchmaking.services import create_game, validate_matchmaking_request


# Tests for "create_game" function
def test_create_game_player_a_with_higher_ratio_as_white(
    test_player_a, test_player_b, test_opponent, test_time_control
):
    """
    Player A has 2 previous games at this time control (1 as white, 1 as black) -> white ratio 0.5.
    Player B has only 1 previous game, as white -> white ratio 1.0.

    Since both players have fewer than 10 games, all of their existing games are used for the ratio
    calculation. Player B's white ratio (1.0) is higher than player A's (0.5), meaning B has played
    white proportionally more often, so B should be assigned black to balance their color history.
    We expect the function will correctly create new game where player A will be assigned as white and
    player B will be assigned as black.
    """

    # Player A's games
    Game.objects.create(
        white_player=test_player_a,
        black_player=test_opponent,
        time_control=test_time_control,
        status=Game.Status.FINISHED,
    )
    Game.objects.create(
        white_player=test_opponent,
        black_player=test_player_a,
        time_control=test_time_control,
        status=Game.Status.FINISHED,
    )

    # Player B's game
    Game.objects.create(
        white_player=test_player_b,
        black_player=test_opponent,
        time_control=test_time_control,
        status=Game.Status.FINISHED,
    )

    game_id = create_game(test_player_a, test_player_b, test_time_control)
    new_game = Game.objects.get(pk=game_id)
    assert new_game.time_control == test_time_control
    assert new_game.white_player == test_player_a
    assert new_game.black_player == test_player_b


def test_create_game_player_a_without_any_game(test_player_a, test_player_b, test_opponent, test_time_control):
    """
    Player A has never played any game at this time control in this case his ratio is 0.5
    because he has never played any game as white and as black.
    Player B has only 1 previous game, as white -> white ratio 1.0.

    We expect that player A will be assigned as white because he has fewer white ratio (0.5)
    and player B will be assigned as black because he has higher white ratio (1.0) than player A.
    """

    Game.objects.create(
        white_player=test_player_b,
        black_player=test_opponent,
        time_control=test_time_control,
        status=Game.Status.FINISHED,
    )
    create_game(test_player_a, test_player_b, test_time_control)
    game_id = create_game(test_player_a, test_player_b, test_time_control)
    new_game = Game.objects.get(pk=game_id)
    assert new_game.time_control == test_time_control
    assert new_game.white_player == test_player_a
    assert new_game.black_player == test_player_b


def test_create_game_both_players_with_the_same_white_ratio(
    test_player_a, test_player_b, test_opponent, test_time_control
):
    """
    In this test both players have never played any game at this time control so they both have white ratio 0.5 and in
    this case when both players have exactly the same white ratio we expect that the function will choose randomly who will
    be played as white and as black.
    """
    game_id = create_game(test_player_a, test_player_b, test_time_control)
    new_game = Game.objects.get(pk=game_id)
    assert new_game.time_control == test_time_control

    assert new_game.white_player == test_player_a or test_player_b
    assert new_game.black_player == test_player_a if new_game.white_player == test_player_b else test_player_b


# Tests for "validate_matchmaking_request" function
def test_validate_matchmaking(test_time_control):
    body = {
        "time_control_id": test_time_control.id,
    }
    time_control = validate_matchmaking_request(body)
    assert time_control == test_time_control


@pytest.mark.parametrize(
    "body, expected_error",
    [
        pytest.param({"test": "test"}, InvalidBody, id="Body without time_control_id"),
        pytest.param({"time_control_id": ""}, InvalidBody, id="Body with empty time_control_id"),
        pytest.param({"time_control_id": "string"}, InvalidBody, id="time_control_id is not int"),
        pytest.param({"time_control_id": 5}, TimeControlNotExist, id="time_control_id with provided id not exists"),
    ],
)
@pytest.mark.django_db
def test_validate_matchmaking_request_invalid_body(body, expected_error):
    with pytest.raises(expected_error):
        validate_matchmaking_request(body)
