from django.db import models
from apps.recordings.models import Recording

class VideoJob(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Ожидает'),
        ('RUNNING', 'В процессе'),
        ('SUCCESS', 'Успешно'),
        ('FAILED', 'Ошибка'),
    ]
    recording = models.ForeignKey(Recording, on_delete=models.CASCADE, related_name='jobs')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    log = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

class Transcript(models.Model):
    job = models.OneToOneField(VideoJob, on_delete=models.CASCADE, related_name='transcript', null=True, blank=True)
    text = models.TextField()
    timestamps = models.JSONField(null=True)

class Summary(models.Model):
    job = models.OneToOneField(VideoJob, on_delete=models.CASCADE, related_name='summary', null=True, blank=True)
    text = models.TextField()

class Notes(models.Model):
    job = models.OneToOneField(VideoJob, on_delete=models.CASCADE, related_name='notes')
    text = models.TextField()
