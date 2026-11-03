from fastapi import FastAPI

from govcheck.api.routes.health import router as health_router

app = FastAPI(
    title="GovCheck AI API",
    version="0.1.0",
    description=(
        "Evidence-grounded support for preliminary analysis of Brazilian public "
        "procurement documents. This service does not provide legal advice."
    ),
)
app.include_router(health_router)
