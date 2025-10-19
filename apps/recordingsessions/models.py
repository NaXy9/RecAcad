from django.db import models
from django.conf import settings
from apps.groups.models import Group


class RecordingSession(models.Model):
    STATUS_CHOICES = [
        ('active', 'Активна'),
        ('stopped', 'Остановлена'),
        ('completed', 'Завершена автоматически'),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='recording_sessions'
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='recording_sessions'
    )
    link = models.URLField(
        max_length=500,
        verbose_name='Ссылка на конференцию',
        blank=True,
        null=True
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    end_time = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Сессия {self.id} ({self.group.title}) — {self.status}"
