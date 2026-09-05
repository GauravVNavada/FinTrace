from functools import lru_cache

from app.core.config import get_settings
from app.persistence.repository import PostgresRepository
from app.repositories.contracts import LifecycleRepository
from app.repositories.sample import SampleRepository, sample_repository


@lru_cache
def get_repository() -> LifecycleRepository:
    settings = get_settings()
    if settings.storage_backend == "postgres":
        return PostgresRepository(settings.database_url)
    return sample_repository


def get_sample_repository() -> SampleRepository:
    return sample_repository
