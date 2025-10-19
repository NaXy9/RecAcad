import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('rekaCad')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks(['apps.processing', 'apps.recordings', 'bot'])
