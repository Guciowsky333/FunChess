from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from accounts.models import CustomUser


# Register your models here.
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ["username", "email", "date_joined"]
