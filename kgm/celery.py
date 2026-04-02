import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kgm.settings')

app = Celery('kgm')
app.config_from_object('django.conf:settings', namespace='CELERY')
print(f"--- [DEBUG] Celery Broker: {app.conf.broker_url} ---", flush=True)
app.autodiscover_tasks()