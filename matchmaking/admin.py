# Register your models here
from django.contrib import admin

from matchmaking.models import AbandonedGame, MatchmakingEntry, TemporaryBan


@admin.register(MatchmakingEntry)
class MatchmakingEntryAdmin(admin.ModelAdmin):
    list_display = ["user_name", "rating", "created_at"]

    def user_name(self, obj):
        return obj.user.username


@admin.register(AbandonedGame)
class AbandonedGameAdmin(admin.ModelAdmin):
    list_display = ["user_name", "user", "created_at"]

    def user_name(self, obj):
        return obj.user.username


@admin.register(TemporaryBan)
class TemporaryBanAdmin(admin.ModelAdmin):
    list_display = ["user_name", "banned_user", "expires_at"]

    def user_name(self, obj):
        return obj.banned_user.username
