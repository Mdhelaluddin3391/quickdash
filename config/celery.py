# config/celery.py (New File)

import os
from celery import Celery
import logging

# Django settings module set karein
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('quickdash')

# Django settings se config load karein (namespace='CELERY')
app.config_from_object('django.conf:settings', namespace='CELERY')

# Saare apps se tasks.py modules ko auto-discover karein
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    logger = logging.getLogger(__name__)
    logger.debug(f'Request: {self.request!r}')