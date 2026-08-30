from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as v1_router
from app.core.config import get_settings
from app.persistence.connection import check_connection

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", docs_url="/docs" if settings.app_env != "production" else None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Actor-Id", "X-Actor-Role", "X-Organization-Id"],
)
app.include_router(v1_router, prefix=settings.api_prefix)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name, "environment": settings.app_env}


@app.get("/ready", tags=["health"])
def readiness() -> dict[str, str]:
    if settings.storage_backend == "postgres" and not check_connection(settings.database_url):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    return {"status": "ready", "storage_backend": settings.storage_backend}
