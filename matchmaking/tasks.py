from asgiref.sync import async_to_sync
from celery import shared_task
from celery.result import AsyncResult
from channels.layers import get_channel_layer
from django.db import transaction

from games.models import TimeControl
from matchmaking.models import MatchmakingEntry
from matchmaking.services import create_game, finding_opponent


@shared_task
def find_opponent_with_large_range(
    user_matchmaking_entry_id: int, time_control_id: int, tolerance: int | None, attempt: int
):
    """
    Task tries to find opponent for provided user MatchmakingEntry object
    First time in MatchMakingConsumer we try to find opponent with tolerance=150
    if function returns None then the first task runs in with tolerance=300 if it returns None
    the second task will run with tolerance=450 and then if it also returns None evry next task
    will be run with unlimited tolerance means that task try to find any opponent regardless of ratings.

    Every next task is runs after 60s
    """
    user_opponent = None
    with transaction.atomic():
        user_matchmaking_entry = (
            MatchmakingEntry.objects.select_for_update().filter(id=user_matchmaking_entry_id).first()
        )
        # If provided user's MatchmakingEntry doesn't exist it means that other player find our user as opponent so task should not do anything
        if not user_matchmaking_entry:
            return

        time_control = TimeControl.objects.get(id=time_control_id)

        best_candidate = finding_opponent(user_matchmaking_entry, time_control, tolerance)
        # If task find the opponent for user
        if best_candidate:
            user_opponent = best_candidate.user
            user = user_matchmaking_entry.user
            game_id = create_game(user_opponent, user_matchmaking_entry.user, time_control)

            # Removes both MatchmakingEntry objects and revoke last task for user's opponent if exist
            if best_candidate.pending_task_id:
                AsyncResult(best_candidate.pending_task_id).revoke()
            best_candidate.delete()
            user_matchmaking_entry.delete()

    # Sends message to both players outside of transaction.atomic()
    if user_opponent:
        channel_layer = get_channel_layer()

        async_to_sync(channel_layer.group_send)(
            f"matchmaking_user_{user.id}", {"type": "match_found", "content": {"game_id": game_id}}
        )

        async_to_sync(channel_layer.group_send)(
            f"matchmaking_user_{user_opponent.id}", {"type": "match_found", "content": {"game_id": game_id}}
        )
        return

    # If task still doesn't find any opponent for our user runs another task with countdown=60s and large renge of tolerance
    if tolerance is not None:
        tolerance += 150
    attempt += 1
    # On the 3 attempt set up tolerance as None it means that now tasks will be run regardless of ratings
    if attempt >= 3:
        tolerance = None
    task = find_opponent_with_large_range.apply_async(
        args=[user_matchmaking_entry_id, time_control_id, tolerance, attempt],
        countdown=60,
    )
    user_matchmaking_entry.pending_task_id = task.id
    user_matchmaking_entry.save()
    return
