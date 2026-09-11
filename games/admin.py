from django.contrib import admin

from games.models import Game, TimeControl


@admin.register(TimeControl)
class TimeControlAdmin(admin.ModelAdmin):
    list_display = ["category", "initial_time_seconds", "increment_seconds"]


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ["id", "result", "status", "time_control_category"]

    def time_control_category(self, obj):
        return obj.time_control.category
