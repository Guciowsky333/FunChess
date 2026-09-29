import random

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


def create_match_making_entry(user: CustomUser, time_control: TimeControl) -> None:
    """
    Take user's rating at provided time_control and creates MatchMakingEntry for user
    """
    user_rating = UserRating.objects.get(
        user=user,
        category=time_control.category,
    ).rating

    MatchmakingEntry.objects.create(
        user=user,
        time_control=time_control,
        rating=user_rating,
    )


def finding_opponent(user_match_making_entry: MatchmakingEntry, time_control: TimeControl) -> MatchmakingEntry | None:
    """
    If found opponent's for user with rating as close as possible to user's rating (max + 150, min -150)
    at provided time_control returns MatchmakingEntry object that contains opponent if not returns None
    """

    # Taking all possible user's opponents with ratings with a rating higher by a maximum of 150 or less by a maximum of 150
    possible_opponents = list(
        MatchmakingEntry.objects.select_for_update()
        .filter(
            time_control=time_control,
            rating__gte=user_match_making_entry.rating - 150,
            rating__lte=user_match_making_entry.rating + 150,
        )
        .exclude(user=user_match_making_entry.user)
    )

    # If currently there is no opponent for user returns None
    if possible_opponents is None:
        return None

    # Selects the best candidate with the closet rating to the user
    best_candidate = None
    best_diff = None
    for candidate in possible_opponents:
        # If candidate has the same rating as user returns it immediately
        if candidate.rating == user_match_making_entry.rating:
            return candidate

        # Uses abs to delete "-" in case where candidate has lowest rating than user
        diff = abs(user_match_making_entry.rating - candidate.rating)

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
