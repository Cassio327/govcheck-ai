from fastapi import FastAPI

from govcheck.api.errors import install_exception_handlers
from govcheck.api.routes.analysis import router as analysis_router
from govcheck.api.routes.chat import router as chat_router
from govcheck.api.routes.documents import router as documents_router
from govcheck.api.routes.health import router as health_router
from govcheck.api.routes.reports import router as reports_router

app = FastAPI(
    title="GovCheck AI API",
    version="0.1.0",
    description=(
        "Evidence-grounded support for preliminary analysis of Brazilian public "
        "procurement documents. This service does not provide legal advice."
    ),
)
install_exception_handlers(app)
app.include_router(health_router)
app.include_router(documents_router)
app.include_router(chat_router)
app.include_router(analysis_router)
app.include_router(reports_router)
