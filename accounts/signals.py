from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.services import create_all_ratings


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_ratings_for_new_user(sender, instance, created, **kwargs):
    if created:
        create_all_ratings(instance)
