from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from accounts.models import CustomUser
from games.models import UserRating


class UserRatingInline(admin.TabularInline):
    model = UserRating
    extra = 0
    can_delete = False
    readonly_fields = ["category", "rating"]


# Register your models here.
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ["username", "email", "date_joined"]
    inlines = [UserRatingInline]
