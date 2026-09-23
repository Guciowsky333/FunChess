from games.models import Game, Move
from games.services import process_move
from games.tasks import check_opponent_time


def test_check_opponent_time_opponent_made_move(test_game):
    """
    Our celery task "check_opponent_time" during real game will run
    when player X (white or black) made a correct move with
    countdown = remaining time of the opponent of the player who made the move.
    The task checks if number of moves is greater than it was at the moment when player X
    made a move. In this test we manually create 2 moves but give ply_number = 1 to our task
    so it should recognize that number of moves is greater than 1 because in game we will habe 2 moves
    and does not do anything with tha game.
    """

    # First and second moves
    process_move(test_game, test_game.white_player, "d2d4")
    process_move(test_game, test_game.black_player, "d7d5")

    # Instead of 2 we give ply_number as 1 it means that player's opponent has already made a move
    ply_number = 1
    check_opponent_time(test_game.id, ply_number)
    test_game.refresh_from_db()
    assert test_game.status == Game.Status.IN_PROGRESS
    assert not test_game.result


def test_check_opponent_time_white_win(test_game_with_updated_ratings):
    """
    In this test we check if "check_opponent_time" celery task correctly
    end the game if black player does not make a move on time.

    Additionally, we check if task "check_opponent_time" correctly updates players ratings
    when any of them didn't make a move on time. In this case white has 1200 and black has 1000 so
    when black doesn't make a move they should lose 8 ratings and white should gain 8 ratings.
    """
    game, white_rating, black_rating = test_game_with_updated_ratings
    game.status = Game.Status.IN_PROGRESS
    game.save()
    # White made the first move
    process_move(game, game.white_player, "d2d4")

    ply_number = game.moves.count()
    check_opponent_time(game.id, ply_number)
    game.refresh_from_db()
    white_rating.refresh_from_db()
    black_rating.refresh_from_db()
    assert game.status == Game.Status.FINISHED
    assert game.reason == Game.Reason.TIMEOUT

    # White should win the game because black was run out of time
    assert game.result == Game.Result.WHITE_WON
    assert game.finished_at is not None

    # Check players ratings when the game is over
    assert white_rating.rating == 1200 + 8
    assert black_rating.rating == 1000 - 8


def test_check_opponent_time_black_win(test_game_with_updated_ratings):
    """
    In this test we check if "check_opponent_time" celery task correctly
    end the game if white player does not make a move on time.

    Additionally, we check if task "check_opponent_time" correctly updates players ratings
    when any of them didn't make a move on time. In this case white has 1200 and black has 1000 so
    when white doesn't make a move they should lose 24 ratings and black should gain 24 ratings.
    """

    game, white_rating, black_rating = test_game_with_updated_ratings
    game.status = Game.Status.IN_PROGRESS
    game.save()

    # White made the first move
    process_move(game, game.white_player, "d2d4")
    # Black made the second move
    process_move(game, game.black_player, "d7d5")

    ply_number = game.moves.count()
    check_opponent_time(game.id, ply_number)
    game.refresh_from_db()
    white_rating.refresh_from_db()
    black_rating.refresh_from_db()
    assert game.status == Game.Status.FINISHED
    assert game.reason == Game.Reason.TIMEOUT

    # Black should win the game because white was run out of time
    assert game.result == Game.Result.BLACK_WON
    assert game.finished_at is not None

    # Check players ratings when the game is over
    assert white_rating.rating == 1200 - 24
    assert black_rating.rating == 1000 + 24


def test_check_opponent_time_has_insufficiently_material(test_game_with_updated_ratings):
    """
    In this test the opponent of the player was run out of time
    but player didn't have enough material to deliver checkmate so he can't win the game.
    The game is finished as draw.

    Additionally, we check if task "check_opponent_time" correctly updates players ratings
    when any of them didn't make a move on time. In this case white has 1200 rating and black has 1000
    and the game is finished as draw so white should lose 8 ratings (Because white has more ratings than black)
    adn blach should gain 8 ratings.
    """

    game, white_rating, black_rating = test_game_with_updated_ratings
    game.status = Game.Status.IN_PROGRESS
    game.save()

    # Create move with fen where white has only king
    Move.objects.create(
        game=game,
        player=game.white_player,
        ply_number=1,
        from_square="e2",
        to_square="e1",
        piece=Move.Piece.KING,
        resulting_fen="4k2r/8/8/8/8/8/8/4K3 b - - 0 30",
    )
    ply_number = game.moves.count()
    check_opponent_time(game.id, ply_number)
    game.refresh_from_db()
    white_rating.refresh_from_db()
    black_rating.refresh_from_db()

    assert game.status == Game.Status.FINISHED
    assert game.reason == Game.Reason.TIMEOUT
    assert game.result == Game.Result.DRAW
    assert game.finished_at is not None

    # Check players ratings when the game is over
    assert white_rating.rating == 1200 - 8
    assert black_rating.rating == 1000 + 8


def test_check_opponent_time_game_status_is_not_in_progress(test_game):
    """
    If game status is other than "IN_PROGRESS" our task should not do anything
    with the game.

    """
    process_move(test_game, test_game.white_player, "d2d4")
    test_game.status = Game.Status.FINISHED
    check_opponent_time(test_game.id, 1)
    # test_game status should be unchanged "FINISHED"
    assert test_game.status == Game.Status.FINISHED
