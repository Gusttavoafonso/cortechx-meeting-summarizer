from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "cortechx_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.meeting_job", "app.workers.partial_job"],
)

celery_app.conf.update(
    task_routes={
        "app.workers.partial_job.consume_partial_session": {
            "queue": "partial_transcription",
        },
    },
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
)
