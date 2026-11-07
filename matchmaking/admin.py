# Register your models here
from django.contrib import admin

from matchmaking.models import MatchmakingEntry


@admin.register(MatchmakingEntry)
class MatchmakingEntryAdmin(admin.ModelAdmin):
    list_display = ["user_name", "rating", "created_at"]

    def user_name(self, obj):
        return obj.user.username
