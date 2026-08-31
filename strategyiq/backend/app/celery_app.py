from celery import Celery

from app.config import settings

celery_app = Celery(
    "strategyiq",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.portfolio"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    result_expires=3600,
)
