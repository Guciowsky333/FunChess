from django.contrib import admin

from games.models import UserRating


@admin.register(UserRating)
class UserRatingAdmin(admin.ModelAdmin):
    list_display = ["user", "get_user_username", "rating", "category"]

    def get_user_username(self, obj):
        return obj.user.username
