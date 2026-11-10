FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml ./
COPY logging.json ./
COPY alembic.ini ./
COPY migrations ./migrations
COPY src ./src

# Keep the lightweight, deterministic demo image by default. Real multilingual
# embeddings are explicitly opt-in because they require large ML dependencies.
ARG INSTALL_EMBEDDINGS=false
RUN if [ "$INSTALL_EMBEDDINGS" = "true" ]; then \
      pip install --no-cache-dir '.[embeddings]'; \
    else \
      pip install --no-cache-dir .; \
    fi && \
    useradd --create-home --uid 10001 govcheck

USER govcheck
EXPOSE 8000
CMD ["uvicorn", "govcheck.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-config", "logging.json", "--no-access-log"]
