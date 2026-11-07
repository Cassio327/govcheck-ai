from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from govcheck.api.errors import install_exception_handlers
from govcheck.api.routes.analysis import router as analysis_router
from govcheck.api.routes.chat import router as chat_router
from govcheck.api.routes.documents import router as documents_router
from govcheck.api.routes.health import router as health_router
from govcheck.api.routes.reports import router as reports_router
from govcheck.config import get_settings

app = FastAPI(
    title="GovCheck AI API",
    version="0.1.0",
    description=(
        "Evidence-grounded support for preliminary analysis of Brazilian public "
        "procurement documents. This service does not provide legal advice."
    ),
)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Session-ID", "Last-Event-ID"],
    expose_headers=["Content-Disposition", "X-Request-ID"],
    max_age=600,
)
install_exception_handlers(app)
app.include_router(health_router)
app.include_router(documents_router)
app.include_router(chat_router)
app.include_router(analysis_router)
app.include_router(reports_router)
