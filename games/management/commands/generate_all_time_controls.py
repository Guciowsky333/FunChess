from django.core.management.base import BaseCommand

from games.models import TimeControl

DEFAULT_TIME_CONTROLS = [
    # All bullets
    (TimeControl.Category.BULLET, 60, 0),
    (TimeControl.Category.BULLET, 60, 1),
    (TimeControl.Category.BULLET, 120, 1),
    # All blitzs
    (TimeControl.Category.BLITZ, 180, 0),
    (TimeControl.Category.BLITZ, 180, 2),
    (TimeControl.Category.BLITZ, 300, 0),
    # All rapids
    (TimeControl.Category.RAPID, 600, 0),
    (TimeControl.Category.RAPID, 600, 5),
    (TimeControl.Category.RAPID, 900, 5),
]


class Command(BaseCommand):
    help = "Creates default TimeControl entries for all game categories"

    def handle(self, *args, **options):
        for category, initial_time_seconds, increment_seconds in DEFAULT_TIME_CONTROLS:
            TimeControl.objects.get_or_create(
                category=category,
                initial_time_seconds=initial_time_seconds,
                increment_seconds=increment_seconds,
            )
