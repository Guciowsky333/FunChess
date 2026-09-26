import random

from django.db.models import Q

from accounts.models import CustomUser
from games.models import Game, TimeControl


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
