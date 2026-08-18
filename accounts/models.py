from django.contrib.auth.models import AbstractUser
from django.db import models

from accounts.managers import CustomUserManager
from accounts.utilis import generate_verification_code

# Create your models here.


class CustomUser(AbstractUser):
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(max_length=150, unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    objects = CustomUserManager()

    def __str__(self):
        return self.username


class VerificationCode(models.Model):
    code = models.CharField(max_length=6, unique=True, default=generate_verification_code)
    email = models.EmailField(max_length=150, unique=True)
