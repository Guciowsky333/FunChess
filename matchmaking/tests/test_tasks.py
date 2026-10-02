from celery.result import AsyncResult
from django.db.models import Q

from games.models import Game
from matchmaking.models import MatchmakingEntry
from matchmaking.tasks import find_opponent_with_large_range


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

    find_opponent_with_large_range(test_player_a_matchmaking_entry.id, test_time_control.id, tolerance=150, attempt=1)

    # Expect that task didn't create a game because it didn't find any opponent for our user
    assert not Game.objects.filter(
        Q(white_player=test_player_a_matchmaking_entry.user) | Q(black_player=test_player_a_matchmaking_entry.user),
        time_control=test_time_control,
    ).exists()
    test_player_a_matchmaking_entry.refresh_from_db()
    # Checks if a new celery task has been established in user's MatchmakingEntry object
    assert test_player_a_matchmaking_entry.pending_task_id is not None


def test_find_opponent_with_large_range_find_opponent(
    test_player_a_matchmaking_entry, test_time_control, test_opponent
):
    """
    In this test we manually create MatchmakingEntry object and run our task with tolerance=150
    but this time our created MatchmakingEntry object is in range of the task's tolerance so expect that task
    find en opponent for the user and create game.

    Additionally: We run task for user's opponent and expect that user's task will revoke his opponent task
    """

    opponent_matchmaking_entry = MatchmakingEntry.objects.create(
        user=test_opponent,
        time_control=test_time_control,
        rating=test_player_a_matchmaking_entry.rating + 149,
    )
    # Run task for opponent with tolerance=1 so it shouldn't find anybody and established pending_task_id in opponent_matchmaking_entry
    find_opponent_with_large_range(opponent_matchmaking_entry.id, test_time_control.id, tolerance=1, attempt=1)
    opponent_matchmaking_entry.refresh_from_db()
    pending_task_id = opponent_matchmaking_entry.pending_task_id

    find_opponent_with_large_range(test_player_a_matchmaking_entry.id, test_time_control.id, tolerance=150, attempt=1)

    assert Game.objects.filter(
        Q(white_player=test_player_a_matchmaking_entry.user) | Q(black_player=test_player_a_matchmaking_entry.user),
        Q(white_player=test_opponent) | Q(black_player=test_opponent),
        time_control=test_time_control,
    ).exists()

    # Expect that task deleted both MatchmakingEntry objects for user and his opponent
    assert not MatchmakingEntry.objects.filter(pk=opponent_matchmaking_entry.id).exists()
    assert not MatchmakingEntry.objects.filter(pk=test_player_a_matchmaking_entry.id).exists()

    # Expect that last opponent's task has been revoked
    result = AsyncResult(pending_task_id)
    assert result.state == "REVOKED"


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
