# =============================================================================
# Base stage - shared dependencies
# =============================================================================
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy AS base

WORKDIR /app

# Install additional build tools and timezone data (Playwright image already has most dependencies)
# Set timezone and frontend to avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Australia/Sydney
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .

# Install CPU-only PyTorch first (lighter, no CUDA)
# Pin to 2.2.0 which has stable CPU wheels available
RUN pip install --no-cache-dir torch==2.2.0 --index-url https://download.pytorch.org/whl/cpu

# Install remaining dependencies
RUN pip install --no-cache-dir -r requirements.txt

RUN pip install pydantic[email]

# Note: Playwright and Chromium are already installed in the base image
# No need to run 'playwright install' again

# =============================================================================
# Test stage - for running tests
# =============================================================================
FROM base AS test

WORKDIR /app

# Copy application and test code
COPY app/ ./app/
COPY tests/ ./tests/
COPY pytest.ini ./

# Set test environment variables
ENV TESTING=true
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Default command runs all tests
CMD ["pytest", "tests/", "-v", "--tb=short"]

# =============================================================================
# Production stage - for running the application
# =============================================================================
FROM base AS production

WORKDIR /app

# Copy application code
COPY app/ ./app/

# Copy hermes-diag CLI tool
COPY hermes-diag /app/hermes-diag
RUN chmod +x /app/hermes-diag

# Create data directories
RUN mkdir -p /app/data/db /app/data/chroma /app/data/linkedin_sessions

# Expose API port
EXPOSE 8000

# Single worker: FastAPI is async so one uvicorn process handles concurrent requests fine.
# Multiple workers would each start their own BackgroundScheduler, causing duplicate
# collection jobs and write contention on the shared SQLite + ChromaDB data.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--timeout-keep-alive", "75"]
