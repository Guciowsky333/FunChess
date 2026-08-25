from django.contrib import admin

from games.models import TimeControl


@admin.register(TimeControl)
class TimeControlAdmin(admin.ModelAdmin):
    list_display = ["category", "initial_time_seconds", "increment_seconds"]
