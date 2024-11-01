from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'shopify_django_app.settings')

app = Celery('shopify_django_app')

# Load configuration from Django settings, using the CELERY namespace
app.config_from_object('django.conf:settings', namespace='CELERY')

# Automatically discover tasks within installed apps
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')

app.conf.beat_schedule = {
    'reset-sort-counts-every-day': {
        'task': 'shopify_app.tasks.reset_sort_counts',  
        'schedule': crontab(hour=0, minute=0),  
    },
}

