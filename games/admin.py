from django.contrib import admin

from games.models import Game, Move, TimeControl, UserRating


@admin.register(TimeControl)
class TimeControlAdmin(admin.ModelAdmin):
    list_display = ["category", "initial_time_seconds", "increment_seconds"]


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ["id", "result", "status", "time_control_category"]

    def time_control_category(self, obj):
        return obj.time_control.category


@admin.register(Move)
class MoveAdmin(admin.ModelAdmin):
    list_display = ["id", "game", "player_name", "ply_number", "from_square", "to_square", "piece"]

    def player_name(self, obj):
        return obj.player.username


@admin.register(UserRating)
class UserRatingAdmin(admin.ModelAdmin):
    list_display = ["user", "rating", "category"]
