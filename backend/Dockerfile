# =============================================================================
# Base stage - pre-built foundation image contains all heavy deps
# (Playwright, torch, all pip packages). Rebuild foundation only when
# requirements.txt or the playwright base image changes:
#   docker build -f Dockerfile.foundation -t your-registry.io/hermes-backend-foundation:latest .
#   docker push your-registry.io/hermes-backend-foundation:latest
# =============================================================================
ARG FOUNDATION_IMAGE=10.10.20.6:5000/nmerrett/hermes-backend-foundation:latest
FROM ${FOUNDATION_IMAGE} AS base

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# =============================================================================
# Test stage - adds test code, used by CI to run unit + integration tests
# =============================================================================
FROM base AS test

COPY app/ ./app/
COPY tests/ ./tests/
COPY pytest.ini ./

ENV TESTING=true

CMD ["pytest", "tests/", "-v", "--tb=short"]

# =============================================================================
# Production stage
# =============================================================================
FROM base AS production

COPY app/ ./app/
COPY hermes-diag /app/hermes-diag
RUN chmod +x /app/hermes-diag
RUN mkdir -p /app/data/db /app/data/chroma /app/data/linkedin_sessions

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--timeout-keep-alive", "75"]
