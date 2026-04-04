import os

from celery import Celery
from app.config import settings

celery_app = Celery(
    "speechpath",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.analysis"],
)

celery_config = {
    "task_serializer": "json",
    "accept_content": ["json"],
    "result_serializer": "json",
    "timezone": "UTC",
    "enable_utc": True,
    "worker_prefetch_multiplier": 1,
    "task_acks_late": True,
    "worker_pool": "solo" if os.name == "nt" else "prefork",
}
if os.name == "nt":
    celery_config["worker_concurrency"] = 1

celery_app.conf.update(**celery_config)
