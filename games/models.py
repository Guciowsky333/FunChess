from django.conf import settings
from django.db import models

from games.validators import validate_chess_square

# Create your models here.


class UserRating(models.Model):
    class Category(models.TextChoices):
        BULLET = "bullet", "Bullet"
        BLITZ = "blitz", "Blitz"
        RAPID = "rapid", "Rapid"

    category = models.CharField(choices=Category.choices, max_length=6)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ratings")
    rating = models.PositiveIntegerField(default=300)

    class Meta:
        """
        User can have only one rating per category.
        """

        constraints = [models.UniqueConstraint(fields=("user", "category"), name="user_rating_unique_category")]


class TimeControl(models.Model):
    class Category(models.TextChoices):
        BULLET = "bullet", "Bullet"
        BLITZ = "blitz", "Blitz"
        RAPID = "rapid", "Rapid"

    category = models.CharField(choices=Category.choices, max_length=6)
    initial_time_seconds = models.PositiveIntegerField()
    increment_seconds = models.PositiveIntegerField(default=0)


class Game(models.Model):
    class Result(models.TextChoices):
        WHITE_WON = "white_won", "White Won"
        BLACK_WON = "black_won", "Black Won"
        DRAW = "draw", "Draw"

    class Status(models.TextChoices):
        WAITING = "waiting", "Waiting"
        IN_PROGRESS = "in_progress", "In Progress"
        FINISHED = "finished", "Finished"

    result = models.CharField(choices=Result.choices, max_length=9, blank=True, null=True)

    status = models.CharField(choices=Status.choices, max_length=11, default=Status.WAITING)
    white_connected = models.BooleanField(default=False)
    black_connected = models.BooleanField(default=False)

    white_player = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="games_as_white")
    black_player = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="games_as_black")
    time_control = models.ForeignKey(TimeControl, on_delete=models.CASCADE, related_name="time_control")

    white_time_remaining = models.PositiveIntegerField(null=True, blank=True)
    black_time_remaining = models.PositiveIntegerField(null=True, blank=True)
    current_turn_started_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)


class Move(models.Model):
    class Piece(models.TextChoices):
        PAWN = "P", "Pawn"
        KNIGHT = "N", "Knight"
        BISHOP = "B", "Bishop"
        ROOK = "R", "Rook"
        QUEEN = "Q", "Queen"
        KING = "K", "King"

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="moves")
    player = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    ply_number = models.PositiveIntegerField()

    # e4 d4 etc
    from_square = models.CharField(max_length=2, validators=[validate_chess_square])
    to_square = models.CharField(max_length=2, validators=[validate_chess_square])

    piece = models.CharField(choices=Piece.choices, max_length=1)
    promotion = models.CharField(choices=Piece.choices, max_length=1, null=True, blank=True)

    resulting_fen = models.CharField(max_length=100)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("game", "ply_number"), name="game_unique_player"),
        ]
