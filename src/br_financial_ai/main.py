from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from br_financial_ai.api.routers.analysis import (
    router as analysis_router,
)
from br_financial_ai.api.routers.companies import router as companies_router
from br_financial_ai.api.routers.financials import (
    router as financials_router,
)
from br_financial_ai.api.routers.market import router as market_router
from br_financial_ai.api.routers.tracked import router as tracked_router
from br_financial_ai.core.settings import cors_origin_list, get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "AI Engineering laboratory for research and analysis "
        "of the Brazilian financial market."
    ),
    version="0.1.0",
)

allowed_origins = cors_origin_list(settings)

if allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Accept"],
    )

app.include_router(companies_router)
app.include_router(financials_router)
app.include_router(analysis_router)
app.include_router(tracked_router)
app.include_router(market_router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "environment": settings.app_environment,
    }
