# Create your models here.
from django.conf import settings
from django.db import models

from games.models import TimeControl


class MatchmakingEntry(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    time_control = models.ForeignKey(TimeControl, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
