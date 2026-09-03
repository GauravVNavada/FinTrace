import logging
import re
from collections import defaultdict, deque
from threading import RLock
from time import monotonic
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import router as v1_router
from app.core.config import get_settings
from app.core.request_context import set_request_id
from app.persistence.connection import check_connection

settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs" if settings.app_env != "production" else None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Idempotency-Key",
        "X-Actor-Id",
        "X-Actor-Role",
        "X-Organization-Id",
    ],
)

_request_logger = logging.getLogger("fintrace.request")
_request_id_pattern = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_rate_limit_lock = RLock()
_write_requests: dict[str, deque[float]] = defaultdict(deque)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    supplied = request.headers.get("X-Request-Id", "")
    request_id = supplied if _request_id_pattern.fullmatch(supplied) else str(uuid4())
    set_request_id(request_id)
    started = monotonic()
    try:
        response = await call_next(request)
    except Exception:
        _request_logger.exception(
            "request_failed method=%s path=%s request_id=%s",
            request.method,
            request.url.path,
            request_id,
        )
        raise
    response.headers["X-Request-Id"] = request_id
    _request_logger.info(
        "request_complete method=%s path=%s status=%s duration_ms=%d request_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        int((monotonic() - started) * 1000),
        request_id,
    )
    return response


@app.middleware("http")
async def write_rate_limit_middleware(request: Request, call_next):
    # Distributed deployments should enforce the same limit at the gateway; this
    # protects the single-process demo/API server from accidental write floods.
    if request.url.path.startswith(settings.api_prefix) and request.method in {
        "POST",
        "PATCH",
        "DELETE",
    }:
        client_identity = request.client.host if request.client else "unknown"
        organization = request.headers.get("X-Organization-Id", "unknown")
        identity = f"{client_identity}:{organization}"
        now = monotonic()
        cutoff = now - settings.rate_limit_window_seconds
        with _rate_limit_lock:
            timestamps = _write_requests[identity]
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            if len(timestamps) >= settings.rate_limit_requests:
                rate_limit_request_id = request.headers.get("X-Request-Id", "")
                if not _request_id_pattern.fullmatch(rate_limit_request_id):
                    rate_limit_request_id = str(uuid4())
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": {"code": "RATE_LIMITED", "message": "Too many write requests"}
                    },
                    headers={
                        "Retry-After": str(settings.rate_limit_window_seconds),
                        "X-Request-Id": rate_limit_request_id,
                    },
                )
            timestamps.append(now)
    return await call_next(request)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if settings.app_env == "production":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


app.include_router(v1_router, prefix=settings.api_prefix)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name, "environment": settings.app_env}


@app.get("/ready", tags=["health"])
def readiness() -> dict[str, str]:
    if settings.storage_backend == "postgres" and not check_connection(settings.database_url):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable"
        )
    return {"status": "ready", "storage_backend": settings.storage_backend}
