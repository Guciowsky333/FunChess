from django.db import models
from django.db.models import Q
from django_filters import rest_framework as filters
from django_filters.rest_framework import DjangoFilterBackend

from games.models import Game


class GameHistoryFilterBackend(DjangoFilterBackend):
    def get_filterset_kwargs(self, request, queryset, view):
        """
        Adding target_user into kwargs using method get_target_user from views.

        Important: target_user is not always request.user.
        In api/game/history/me target_user is request user but in api/games/history/username/
        target_user is a player with provided username if exists.
        """
        kwargs = super().get_filterset_kwargs(request, queryset, view)
        kwargs["target_user"] = view.get_target_user()
        return kwargs


def filter_category(queryset, name, value):
    return queryset.filter(time_control__category=value)


class GameHistoryFilter(filters.FilterSet):
    def __init__(self, *args, target_user, **kwargs):
        """
        Set up target_user from kwargs into our object
        """
        super().__init__(*args, **kwargs)
        self.target_user = target_user

    class Result(models.TextChoices):
        WIN = (
            "win",
            "win",
        )
        LOSE = "lose", "lose"
        DRAW = "draw", "draw"

    class Color(models.TextChoices):
        WHITE = "white", "white"
        BLACK = "black", "black"

    class Category(models.TextChoices):
        BULLET = "bullet", "Bullet"
        BLITZ = "blitz", "Blitz"
        RAPID = "rapid", "Rapid"

    result = filters.ChoiceFilter(choices=Result.choices, method="filter_result")
    color = filters.ChoiceFilter(choices=Color.choices, method="filter_color")
    category = filters.ChoiceFilter(
        field_name="time_control__category",
        choices=Category.choices,
    )

    def filter_result(self, queryset, name, value):
        if value == "win":
            # Returns only games where our target_user won
            user = self.target_user
            return queryset.filter(
                Q(white_player=user, result=Game.Result.WHITE_WON) | Q(black_player=user, result=Game.Result.BLACK_WON)
            )
        if value == "lose":
            # Returns only games where our target_user lost
            user = self.target_user
            return queryset.filter(
                Q(white_player=user, result=Game.Result.BLACK_WON) | Q(black_player=user, result=Game.Result.WHITE_WON)
            )
        return queryset.filter(result=Game.Result.DRAW)

    def filter_color(self, queryset, name, value):
        user = self.target_user
        if value == "white":
            return queryset.filter(white_player=user)
        return queryset.filter(black_player=user)
