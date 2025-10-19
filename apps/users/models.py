from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=150, blank=True)

    def __str__(self):
            if self.first_name or self.last_name:
                return f"{self.first_name} {self.last_name} ({self.username})"
            return self.username

