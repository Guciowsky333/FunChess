# Create your models here.
from django.conf import settings
from django.db import models

from games.models import TimeControl


class MatchmakingEntry(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    time_control = models.ForeignKey(TimeControl, on_delete=models.CASCADE)

    # This filed is taken from user rating at provided time control in function "create_match_making_entry" in services.py
    rating = models.PositiveIntegerField()

    # id of last called task 'find_opponent_with_large_range' during create a game
    pending_task_id = models.CharField(max_length=36, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
