from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from django.db.models import Q
from django.utils import timezone

from games.models import Game
from matchmaking.models import AbandonedGame, MatchmakingEntry, TemporaryBan
from matchmaking.tasks import abandon_game_if_not_started, find_opponent_with_large_range


# Tests for 'find_opponent_with_large_range' task
@pytest.mark.django_db(transaction=True)
def test_find_opponent_with_large_range_not_find_opponent(
    test_player_a_matchmaking_entry, test_time_control, test_opponent
):
    """
    In this test we manually create MatchmakingEntry object and run our task with tolerance 150
    The MatchmakingEntry object has too high rating (151 greater than out user) and expect that our task
    doesn't take this MatchmakingEntry into account and runs another task with greater tolerance
    """
    MatchmakingEntry.objects.create(
        user=test_opponent,
        time_control=test_time_control,
        rating=test_player_a_matchmaking_entry.rating + 151,
    )

    # Mock apply_async so the task doesn't recursively run with wider tolerance in eager test mode
    with patch("matchmaking.tasks.find_opponent_with_large_range.apply_async") as mock_apply_async:
        mock_apply_async.return_value.id = "fake-task-id"
        find_opponent_with_large_range(
            test_player_a_matchmaking_entry.id, test_time_control.id, tolerance=150, attempt=1
        )

    # Expect that task didn't create a game because it didn't find any opponent for our user
    assert not Game.objects.filter(
        Q(white_player=test_player_a_matchmaking_entry.user) | Q(black_player=test_player_a_matchmaking_entry.user),
        time_control=test_time_control,
    ).exists()
    test_player_a_matchmaking_entry.refresh_from_db()
    # Checks if a new celery task has been established in user's MatchmakingEntry object
    assert test_player_a_matchmaking_entry.pending_task_id is not None


@pytest.mark.django_db(transaction=True)
def test_find_opponent_with_large_range_find_opponent(
    test_player_a_matchmaking_entry, test_time_control, test_opponent
):
    """
    In this test we manually create MatchmakingEntry object and run our task with tolerance=150
    but this time our created MatchmakingEntry object is in range of the task's tolerance so expect that task
    find en opponent for the user and create game.
    """

    opponent_matchmaking_entry = MatchmakingEntry.objects.create(
        user=test_opponent,
        time_control=test_time_control,
        rating=test_player_a_matchmaking_entry.rating + 149,
    )

    find_opponent_with_large_range(test_player_a_matchmaking_entry.id, test_time_control.id, tolerance=150, attempt=1)

    assert Game.objects.filter(
        Q(white_player=test_player_a_matchmaking_entry.user) | Q(black_player=test_player_a_matchmaking_entry.user),
        Q(white_player=test_opponent) | Q(black_player=test_opponent),
        time_control=test_time_control,
    ).exists()

    # Expect that task deleted both MatchmakingEntry objects for user and his opponent
    assert not MatchmakingEntry.objects.filter(pk=opponent_matchmaking_entry.id).exists()
    assert not MatchmakingEntry.objects.filter(pk=test_player_a_matchmaking_entry.id).exists()


@pytest.mark.django_db(transaction=True)
def test_find_opponent_with_large_range_third_attempt(
    test_player_a_matchmaking_entry, test_time_control, test_opponent
):
    """
    This test runs task with attempt=3, and tolerance as None. After 3 attempts task tries to find any opponent
    regardless of rating.
    """
    # MatchmakingEntry with rating greater by 1000 than our user still should be found with tolerance None
    opponent_matchmaking_entry = MatchmakingEntry.objects.create(
        user=test_opponent,
        time_control=test_time_control,
        rating=test_player_a_matchmaking_entry.rating + 1000,
    )
    # Even if tolerance is set as 150 task still should overwrite this when attempt is 3 or greater
    find_opponent_with_large_range(test_player_a_matchmaking_entry.id, test_time_control.id, attempt=3, tolerance=None)
    assert Game.objects.filter(
        Q(white_player=test_player_a_matchmaking_entry.user) | Q(black_player=test_player_a_matchmaking_entry.user),
        Q(white_player=test_opponent) | Q(black_player=test_opponent),
        time_control=test_time_control,
    ).exists()
    # Expect that task deleted both MatchmakingEntry objects for user and his opponent
    assert not MatchmakingEntry.objects.filter(pk=opponent_matchmaking_entry.id).exists()
    assert not MatchmakingEntry.objects.filter(pk=test_player_a_matchmaking_entry.id).exists()


# Tests for 'abandon_game_if_not_started' task
@pytest.mark.parametrize(
    "game_status",
    [
        pytest.param("waiting", id="status_waiting"),
        pytest.param("in_progress", id="status_in_progress"),
        pytest.param("finished", id="status_finished"),
    ],
)
def test_abandon_game_if_not_started_all_game_statuses(game_status, test_game):
    """
    If game have status "waiting" our task should finish the game with result "ABANDONED"
    otherwise shouldn't do anything.
    """
    test_game.status = game_status
    test_game.save()
    abandon_game_if_not_started(test_game.id)
    test_game.refresh_from_db()

    if game_status == "waiting":
        assert test_game.status == Game.Status.FINISHED
        assert test_game.result == Game.Result.ABANDONED
    # If status is other than "WAITING" game result and status should be the same
    else:
        assert test_game.status == game_status
        assert not test_game.result


@pytest.mark.parametrize(
    "white_jointed, black_jointed, expected",
    [
        pytest.param(False, True, ["white"], id="white didn't join"),
        pytest.param(True, False, ["black"], id="black didn't join"),
        pytest.param(False, False, ["white", "black"], id="both didn't join"),
    ],
)
def test_abandon_task_sends_not_connected_players(white_jointed, black_jointed, expected, test_game, mocker):
    """
    In this test we check if our task correctly sends message with players who didn't join to the game
    """
    fake_layer = MagicMock()
    fake_layer.group_send = AsyncMock()
    mocker.patch("matchmaking.tasks.get_channel_layer", return_value=fake_layer)

    test_game.white_joined = white_jointed
    test_game.black_joined = black_jointed
    test_game.save()

    abandon_game_if_not_started(test_game.id)

    fake_layer.group_send.assert_awaited_once()
    group, message = fake_layer.group_send.await_args.args

    assert group == f"game_{test_game.id}"
    assert message["type"] == "game_ended"
    assert message["content"]["not_connected_players"] == expected


def test_white_did_not_join_5_time_per_day(test_game):
    """
    In this test white didn't join to his game, but it was his 5 times during 24 hours
    when he didn't join to a game we expect that task will create TemporaryBan for white player for
    30 minutes
    """

    # Create 4 AbandonedGame for white
    for _ in range(4):
        AbandonedGame.objects.create(
            user=test_game.white_player,
        )

    abandon_game_if_not_started(test_game.id)
    assert (
        AbandonedGame.objects.filter(
            user=test_game.white_player,
            created_at__gte=timezone.now() - timedelta(hours=24),
        ).count()
        == 5
    )
    assert TemporaryBan.objects.filter(
        banned_user=test_game.white_player,
    ).exists()
