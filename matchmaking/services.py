import random

from django.db import transaction
from django.db.models import Q

from accounts.models import CustomUser
from games.models import Game, TimeControl, UserRating
from matchmaking.exceptions import InvalidBody, TimeControlNotExist
from matchmaking.models import MatchmakingEntry


def validate_matchmaking_request(body: dict) -> TimeControl:
    """
    Validates body in MatchMakingConsumer in this consumer users are enable to send only
    time_control filed that must contains id of existing TimeControl object if all validations will pass
    returns TimeControl object with provided id
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
    Take user's rating at provided time_control and creates MatchMakingEntry for user
    """
    user_rating = UserRating.objects.get(
        user=user,
        category=time_control.category,
    ).rating

    return MatchmakingEntry.objects.create(
        user=user,
        time_control=time_control,
        rating=user_rating,
    )


def finding_opponent(
    user_matchmaking_entry: MatchmakingEntry,
    time_control: TimeControl,
    tolerance: int = 150,
) -> MatchmakingEntry | None:
    """
    Finds the best available opponent for a user searching for a match at a given time control.

    Looks up MatchmakingEntry objects at the same time_control, excluding the user's own entry,
    whose rating differs from the user's rating by at most `tolerance` in either direction.
    Returns the candidate with the closest rating (an exact match is returned immediately);
    returns None if no candidate falls within the tolerance.
    """

    # Taking all possible user's opponents with ratings with a rating higher by a maximum of 150 or less by a maximum of 150
    possible_opponents = list(
        MatchmakingEntry.objects.select_for_update()
        .filter(
            time_control=time_control,
            rating__gte=user_matchmaking_entry.rating - tolerance,
            rating__lte=user_matchmaking_entry.rating + tolerance,
        )
        .exclude(user=user_matchmaking_entry.user)
    )

    # If currently there is no opponent for user returns None
    if possible_opponents is None:
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


def search_for_match(
    user: CustomUser, time_control: TimeControl
) -> tuple[bool, MatchmakingEntry | None, None | int, None | CustomUser]:
    """
    This function combines 'create_matchmaking_entry', 'finding_opponent' and 'create_game' and wraps them
    in transaction.atomic to roll back all of them if something goes wrong.

    Uses a game_created flag: if False, finding_opponent didn't find an opponent, and the function returns
    user_matchmaking_entry so a celery task can try to find an opponent again with a wider tolerance for the user.
    If True, finding_opponent found the user's opponent and create_game created the game, so the function returns
    game_id and the opponent's CustomUser to send a message about the found game to the user's opponent.

    Important: the returned tuple always has length 4, in the same order:
    (game_created, MatchmakingEntry object for user, game_id, CustomUser object for user's opponent) — even when
    some of those fields aren't relevant for the given outcome, they are filled in as None.
    """
    with transaction.atomic():
        user_matchmaking_entry = create_matchmaking_entry(user, time_control)
        user_opponent_matchmaking_entry = finding_opponent(user_matchmaking_entry, time_control, tolerance=150)
        if user_opponent_matchmaking_entry is None:
            game_created = False
            return game_created, user_matchmaking_entry, None, None

        game_id = create_game(user_matchmaking_entry.user, user_opponent_matchmaking_entry.user, time_control)
        game_created = True
        user_opponent = user_opponent_matchmaking_entry.user
        # Removes user and his opponent MatchmakingEntry objects when the game has been created for them successfully
        user_opponent_matchmaking_entry.delete()
        user_matchmaking_entry.delete()

        return game_created, None, game_id, user_opponent
