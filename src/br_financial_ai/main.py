from fastapi import FastAPI

from br_financial_ai.core.settings import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "AI Engineering laboratory for research and analysis "
        "of the Brazilian financial market."
    ),
    version="0.1.0",
)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "environment": settings.app_environment,
    }
