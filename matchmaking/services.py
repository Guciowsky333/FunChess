import random

from celery.result import AsyncResult
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import CustomUser
from games.models import Game, TimeControl, UserRating
from games.services import calculate_elo_change
from matchmaking.exceptions import (
    AlreadySearching,
    InvalidBody,
    TimeControlNotExist,
    YouAlreadyHaveGameInProgress,
    YouAreTemporaryBanned,
)
from matchmaking.models import MatchmakingEntry, TemporaryBan


def validate_matchmaking_request(body: dict) -> TimeControl:
    """
    Validates body in MatchMakingConsumer in this consumer users are enable to send only
    time_control filed that must contains id of existing TimeControl object if all validations will pass
    returns TimeControl object with provided id.
    """

    time_control_id = body.get("time_control_id")

    # Body must contain time_control_id key
    if time_control_id is None:
        raise InvalidBody

    # Value of time_control_id must be int
    if not isinstance(time_control_id, int):
        raise InvalidBody

    # Object TimeControl with provided id must exist
    try:
        return TimeControl.objects.get(id=time_control_id)
    except TimeControl.DoesNotExist:
        raise TimeControlNotExist


def create_matchmaking_entry(user: CustomUser, time_control: TimeControl) -> MatchmakingEntry:
    """
    Take user's rating at provided time_control and creates MatchMakingEntry for user.

    Important: User can't have 2 or more MatchMakingEntry objects at once and user can't
    have any game in status "WAITING" or "IN_PROGRESS" when function try to create MatchMakingEntry for him.

    Important: Function checks whether user don't have temporary ban for finding games
    """

    # Checks if user has any active ban
    now = timezone.now()
    ban = (
        TemporaryBan.objects.filter(
            banned_user=user,
            expires_at__gte=now,
        )
        .order_by("-expires_at")
        .first()
    )
    if ban:
        raise YouAreTemporaryBanned(ban.expires_at)

    # Checks if user has any game in progress
    if Game.objects.filter(
        Q(white_player=user) | Q(black_player=user),
        status__in=[Game.Status.WAITING, Game.Status.IN_PROGRESS],
    ).exists():
        raise YouAlreadyHaveGameInProgress

    user_rating = UserRating.objects.get(
        user=user,
        category=time_control.category,
    ).rating

    try:
        return MatchmakingEntry.objects.create(
            user=user,
            time_control=time_control,
            rating=user_rating,
        )
    except IntegrityError:
        raise AlreadySearching


def finding_opponent(
    user_matchmaking_entry: MatchmakingEntry,
    time_control: TimeControl,
    tolerance: None | int = 150,
) -> MatchmakingEntry | None:
    """
    Finds the best available opponent for a user searching for a match at a given time control.

    Looks up MatchmakingEntry objects at the same time_control, excluding the user's own entry,
    whose rating differs from the user's rating by at most `tolerance` in either direction.
    Returns the candidate with the closest rating (an exact match is returned immediately);
    returns None if no candidate falls within the tolerance.

    If tolerance is None taking all MatchmakingEntry objects at provided time_control regardless of ratings
    """

    # Taking all possible user's opponents with ratings with a rating higher by a maximum of 150 or less by a maximum of 150
    queryset = (
        MatchmakingEntry.objects.select_for_update()
        .filter(time_control=time_control)
        .exclude(user=user_matchmaking_entry.user)
    )

    if tolerance is not None:
        queryset = queryset.filter(
            rating__gte=user_matchmaking_entry.rating - tolerance,
            rating__lte=user_matchmaking_entry.rating + tolerance,
        )
    possible_opponents = list(queryset)

    # If currently there is no opponent for user returns None
    if not possible_opponents:
        return None

    # Selects the best candidate with the closet rating to the user
    best_candidate = None
    best_diff = None
    for candidate in possible_opponents:
        # If candidate has the same rating as user returns it immediately
        if candidate.rating == user_matchmaking_entry.rating:
            return candidate

        # Uses abs to delete "-" in case where candidate has lowest rating than user
        diff = abs(user_matchmaking_entry.rating - candidate.rating)

        # If current candidate has smaller diff than previous one he becomes new best_candidate
        if best_diff is None or diff < best_diff:
            best_candidate = candidate
            best_diff = diff

    return best_candidate


def _determine_players_color(
    player_a: CustomUser, player_b: CustomUser, time_control: TimeControl
) -> tuple[CustomUser, CustomUser]:
    """
    This function take last 10 games of both players in provided time control or all games if player doesn't have 10 games yet and checks which player
    has a higher ratio as white player. If player a has higher ratio he will play as black in this game

    Important: If both players has exactly the same ration then we choos random player who will play as white and as black.
    """

    # Counts player_a ration as white
    player_a_last_games = list(
        Game.objects.filter(
            Q(white_player=player_a) | Q(black_player=player_a),
            time_control=time_control,
            status=Game.Status.FINISHED,
        ).order_by("-created_at")[:10]
    )

    if player_a_last_games:
        player_a_ration_as_white = round(
            sum(1 for game in player_a_last_games if game.white_player == player_a) / len(player_a_last_games), 2
        )

    # If player has 0 games in this time control sets his ratio as 0,5
    else:
        player_a_ration_as_white = 0.5

    # Counts player_b ration as white
    player_b_last_games = list(
        Game.objects.filter(
            Q(white_player=player_b) | Q(black_player=player_b),
            time_control=time_control,
            status=Game.Status.FINISHED,
        ).order_by("-created_at")[:10]
    )

    if player_b_last_games:
        player_b_ration_as_white = round(
            sum(1 for game in player_b_last_games if game.white_player == player_b) / len(player_b_last_games), 2
        )

    # If player has 0 games in this time control sets his ratio as 0,5
    else:
        player_b_ration_as_white = 0.5

    if player_a_ration_as_white > player_b_ration_as_white:
        white_player = player_b
        black_player = player_a

    elif player_b_ration_as_white > player_a_ration_as_white:
        white_player = player_a
        black_player = player_b

    # If players have the same ration we choose white and black player randomly
    else:
        white_player = random.choice([player_a, player_b])
        black_player = player_a if white_player == player_b else player_b

    return white_player, black_player


def create_game(player_a: CustomUser, player_b: CustomUser, time_control: TimeControl) -> int:
    """
    Creates a game and returns its id
    """

    # Establishes who should play as white and who as black
    white_player, black_player = _determine_players_color(player_a, player_b, time_control)

    game = Game.objects.create(
        white_player=white_player,
        black_player=black_player,
        time_control=time_control,
    )
    return game.id


RatingChanges = dict[str, int]


def show_ratings_changes(
    user_matchmaking_entry: MatchmakingEntry, opponent_matchmaking_entry: MatchmakingEntry
) -> tuple[RatingChanges, RatingChanges]:
    """
    Returns 2 dict, one contain how many rating points our user will lose or gain depends on the game result, and second one contain
    how many rating points user's opponent will lose or gain depends on the game result.

    Uses calculate_elo_change function that
    """
    user_rating = user_matchmaking_entry.rating
    opponent_rating = opponent_matchmaking_entry.rating

    user_rating_changes = {
        # 1 means user won the game
        "win": calculate_elo_change(user_rating, opponent_rating, 1),
        # 0.5 means user drew the game
        "draw": calculate_elo_change(user_rating, opponent_rating, 0.5),
        # 0 means user lost the game
        "lose": calculate_elo_change(user_rating, opponent_rating, 0),
    }

    opponent_rating_changes = {
        # 1 means opponent won the game
        "win": calculate_elo_change(opponent_rating, user_rating, 1),
        # 0.5 means opponent drew the game
        "draw": calculate_elo_change(opponent_rating, user_rating, 0.5),
        # 0 means opponent lost the game
        "lose": calculate_elo_change(opponent_rating, user_rating, 0),
    }

    return user_rating_changes, opponent_rating_changes


def search_for_match(
    user: CustomUser, time_control: TimeControl
) -> tuple[bool, MatchmakingEntry | None, None | int, None | CustomUser, dict | None, dict | None]:
    """
    This function combines 'create_matchmaking_entry', 'finding_opponent' and 'create_game' and wraps them
    in transaction.atomic to roll back all of them if something goes wrong.

    Uses a game_created flag: if False, finding_opponent didn't find an opponent, and the function returns
    user_matchmaking_entry so a celery task can try to find an opponent again with a wider tolerance for the user.
    If True, finding_opponent found the user's opponent and create_game created the game, so the function returns
    game_id and the opponent's CustomUser to send a message about the found game to the user's opponent.

    Important: the returned tuple always has length 6, in the same order:
    (game_created, MatchmakingEntry object for user, game_id, CustomUser object for user's opponent,
    user_rating_changes if game has been created, opponent_rating_changes if game has been created) — even when
    some of those fields aren't relevant for the given outcome, they are filled in as None.

    Function also uses _show_ratings_changes to show how many rating points
    players will gain or lose depending on the game result but only when found opponent and created a game.
    """
    with transaction.atomic():
        user_matchmaking_entry = create_matchmaking_entry(user, time_control)
        user_opponent_matchmaking_entry = finding_opponent(user_matchmaking_entry, time_control, tolerance=150)
        if user_opponent_matchmaking_entry is None:
            game_created = False
            return game_created, user_matchmaking_entry, None, None, None, None

        # Calculates ratings changes after the game to show them for the players before the game has beed started
        user_rating_changes, opponent_rating_changes = show_ratings_changes(
            user_matchmaking_entry, user_opponent_matchmaking_entry
        )

        game_id = create_game(user_matchmaking_entry.user, user_opponent_matchmaking_entry.user, time_control)
        game_created = True
        user_opponent = user_opponent_matchmaking_entry.user
        # Removes user and his opponent MatchmakingEntry objects when the game has been created for them successfully
        if user_opponent_matchmaking_entry.pending_task_id:
            AsyncResult(user_opponent_matchmaking_entry.pending_task_id).revoke()
        user_opponent_matchmaking_entry.delete()
        user_matchmaking_entry.delete()

        return game_created, None, game_id, user_opponent, user_rating_changes, opponent_rating_changes


def delete_matchmaking_entry_after_disconnect(user: CustomUser):
    """
    This function is uses only when user disconnected from MatchMakingConsumer, it checks if user
    still has MatchmakingEntry object and delete it and revoke last task
    """

    user_matchmaking_entry = MatchmakingEntry.objects.filter(user=user).first()
    if user_matchmaking_entry:
        if user_matchmaking_entry.pending_task_id:
            AsyncResult(user_matchmaking_entry.pending_task_id).revoke()
        user_matchmaking_entry.delete()

    return


def check_if_user_has_temporary_ban(user: CustomUser) -> dict:
    """
    Returns TemporaryBan's expires time if user has active temporary ban.
    """
    now = timezone.now()
    user_temporary_ban = (
        TemporaryBan.objects.filter(banned_user=user, expires_at__gte=now).order_by("-expires_at").first()
    )
    if user_temporary_ban:
        return {"banned": True, "expires_at": user_temporary_ban.expires_at.isoformat(timespec="seconds")}
    return {"banned": False, "expires_at": ""}
