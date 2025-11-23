FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

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
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install remaining dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Note: Playwright and Chromium are already installed in the base image
# No need to run 'playwright install' again

# Copy application code
COPY app/ ./app/

# Copy hermes-diag CLI tool
COPY hermes-diag /app/hermes-diag
RUN chmod +x /app/hermes-diag

# Create data directories
RUN mkdir -p /app/data/db /app/data/chroma /app/data/linkedin_sessions

# Expose API port
EXPOSE 8000

# Run the application with multiple workers for concurrent request handling
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--timeout-keep-alive", "75"]
