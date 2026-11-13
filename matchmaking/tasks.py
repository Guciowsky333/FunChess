from datetime import timedelta

from asgiref.sync import async_to_sync
from celery import shared_task
from celery.result import AsyncResult
from channels.layers import get_channel_layer
from django.db import transaction
from django.utils import timezone

from games.models import Game, TimeControl
from matchmaking.models import AbandonedGame, MatchmakingEntry, TemporaryBan
from matchmaking.services import create_game, finding_opponent, show_ratings_changes


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
    channel_layer = get_channel_layer()
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
            # Calculates ratings changes after the game to show them for the players before the game has beed started
            user_rating_changes, opponent_rating_changes = show_ratings_changes(user_matchmaking_entry, best_candidate)

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
        async_to_sync(channel_layer.group_send)(
            f"matchmaking_user_{user.id}",
            {
                "type": "match_found",
                "content": {"game_id": game_id, "rating_changes": user_rating_changes},
            },
        )

        async_to_sync(channel_layer.group_send)(
            f"matchmaking_user_{user_opponent.id}",
            {
                "type": "match_found",
                "content": {"game_id": game_id, "rating_changes": opponent_rating_changes},
            },
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
    async_to_sync(channel_layer.group_send)(
        f"matchmaking_user_{user_matchmaking_entry.user.id}",
        {"type": "searching", "content": {"searching": "Wait still find your opponent"}},
    )

    return


@shared_task
def abandon_game_if_not_started(game_id: int):
    """
    This task check if players connected to the game and the game hase been started.

    When MatchMakingConsumer find opponent and create a game both players have 30s to connect to the game
    if any of them don't do it the game is finished with result "ABANDONED".

    Additionally: If a player didn't connect to his game creates AbandonedGame object for this user
    if a user has 5 AbandonedGame objects during 24 hours he will receive Ban for 30 minutes for finding games.
    """
    channel_layer = get_channel_layer()
    with transaction.atomic():
        game = Game.objects.select_for_update().get(id=game_id)

        # If the game already has been started task shouldn't do anything
        if game.status != Game.Status.WAITING:
            return

        game.status = Game.Status.FINISHED
        game.result = Game.Result.ABANDONED
        game.save()

        # Checking who didn't connect to the game and send message to players
        not_connected = []
        if not game.white_joined:
            not_connected.append("white")

            AbandonedGame.objects.create(
                user=game.white_player,
            )
            # Checks if white_player has 5 AbandonedGame during last 24 hours
            recent_abandoned_games = AbandonedGame.objects.filter(
                user=game.white_player,
                created_at__gte=timezone.now() - timedelta(hours=24),
            ).count()

            if recent_abandoned_games >= 5:
                # Creates temporary ban for 30 minutes for user
                TemporaryBan.objects.create(
                    banned_user=game.white_player,
                    expires_at=timezone.now() + timedelta(minutes=30),
                )

        if not game.black_joined:
            not_connected.append("black")
            AbandonedGame.objects.create(
                user=game.black_player,
            )
            # Checks if black_player has 5 AbandonedGame during last 24 hours
            recent_abandoned_games = AbandonedGame.objects.filter(
                user=game.black_player,
                created_at__gte=timezone.now() - timedelta(hours=24),
            ).count()

            if recent_abandoned_games >= 5:
                # Creates temporary ban for 30 minutes for user
                TemporaryBan.objects.create(
                    banned_user=game.black_player,
                    expires_at=timezone.now() + timedelta(minutes=30),
                )

    async_to_sync(channel_layer.group_send)(
        f"game_{game.id}",
        {"type": "game_ended", "content": {"result": game.result, "not_connected_players": not_connected}},
    )
    return
