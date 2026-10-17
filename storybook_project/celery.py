import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "storybook_project.settings")

app = Celery("storybook_project")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
