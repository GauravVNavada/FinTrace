from fastapi import APIRouter

from app.api.v1.routes import (
    analytics,
    controls,
    dashboard,
    exceptions,
    financial_investigations,
    investigations,
    lifecycles,
)

router = APIRouter()
router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
router.include_router(exceptions.router, prefix="/exceptions", tags=["exceptions"])
router.include_router(lifecycles.router, prefix="/lifecycles", tags=["lifecycles"])
router.include_router(investigations.router, tags=["investigations"])
router.include_router(controls.router, tags=["controls"])
router.include_router(analytics.router, tags=["analytics"])
router.include_router(
    financial_investigations.router,
    prefix="/financial-investigations",
    tags=["financial-investigations"],
)
