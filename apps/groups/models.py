from django.db import models
from django.conf import settings

class Group(models.Model):
    title = models.CharField(max_length=100)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='owned_groups'
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name='member_groups', blank=True
    )

    def __str__(self):
        return self.title
