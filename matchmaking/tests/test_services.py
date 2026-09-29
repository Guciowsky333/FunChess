import pytest

from games.models import Game, UserRating
from matchmaking.exceptions import InvalidBody, TimeControlNotExist
from matchmaking.models import MatchmakingEntry
from matchmaking.services import create_game, create_match_making_entry, finding_opponent, validate_matchmaking_request


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


# Tests for "create_match_making_entry" function
def test_create_match_making_entry(test_player_a, test_time_control):
    """
    In this test we set up test_player_a rating at test_time_control as 1000 and expect
    that our function will correctly create MatchMakingEntry for user
    """
    test_player_a_rating = UserRating.objects.get(user=test_player_a, category=test_time_control.category)
    test_player_a_rating.rating = 1000
    test_player_a_rating.save()

    create_match_making_entry(test_player_a, test_time_control)
    assert MatchmakingEntry.objects.filter(user=test_player_a, time_control=test_time_control, rating=1000).exists()


# Tests for "finding_opponent" function
def test_finding_opponent_returns_opponent_with_closet_rating(
    test_player_a_matchmaking_entry, test_time_control, test_player_b, test_opponent
):
    """
    test_player_a_matchmaking_entry has rating 1000

    In this test we manually create 2 MatchmakingEntry with test_time_control
    one with 1010 so diff between user's rating is 10 and second with rating 991 so diff between user's rating is 9,
    and we expect that our function return second MatchmakingEntry object with 991 rating.
    """

    MatchmakingEntry.objects.create(
        user=test_player_b,
        time_control=test_time_control,
        rating=1010,
    )

    second_matchmaking_entry = MatchmakingEntry.objects.create(
        user=test_opponent,
        time_control=test_time_control,
        rating=991,
    )

    best_opponent = finding_opponent(test_player_a_matchmaking_entry, test_time_control)
    assert best_opponent == second_matchmaking_entry


def test_find_opponent_returns_none_when_no_entry_in_range(
    test_player_a_matchmaking_entry, test_time_control, test_player_b, test_opponent
):
    """
    Function "find_opponent" takes into accounts only players with maximum 150 ratings more that current user or maximum 150 less rating
    than current user.

    In this test we manually create 2 MatchmakingEntry with test_time_control but this time the first one will be
    with too higher rating more than user's rating by 151 and second one will be with too low rating less than user's rating by 151.
    Expect that function doesn't find any opponent and return "None"
    """

    # MatchmakingEntry higher by 151 points than test_player_a rating
    MatchmakingEntry.objects.create(
        user=test_player_b,
        time_control=test_time_control,
        rating=test_player_a_matchmaking_entry.rating + 151,
    )
    # MatchmakingEntry lower by 151 points than test_player_a rating
    MatchmakingEntry.objects.create(
        user=test_opponent,
        time_control=test_time_control,
        rating=test_player_a_matchmaking_entry.rating - 151,
    )
    best_opponent = finding_opponent(test_player_a_matchmaking_entry, test_time_control)
    assert best_opponent is None


def test_find_opponent_returns_none_when_nobody_else_is_finding_game(
    test_player_a_matchmaking_entry, test_time_control
):
    """
    In this test there is only one MatchmakingEntry with test_time_control "test_player_a_matchmaking_entry" so expect
    that for test_player_a function will return "None" because nobody elso is finding game right now.
    """
    best_opponent = finding_opponent(test_player_a_matchmaking_entry, test_time_control)
    assert best_opponent is None


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
