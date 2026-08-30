from functools import lru_cache

from app.core.config import get_settings
from app.persistence.repository import PostgresRepository
from app.repositories.contracts import LifecycleRepository
from app.repositories.demo import DemoRepository, demo_repository


@lru_cache
def get_repository() -> LifecycleRepository:
    settings = get_settings()
    if settings.storage_backend == "postgres":
        return PostgresRepository(settings.database_url)
    return demo_repository


def get_demo_repository() -> DemoRepository:
    return demo_repository
